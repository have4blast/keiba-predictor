"""LightGBM 学習モジュール（GroupKFold + 勝利/複勝 2モデル）"""
import json
from datetime import datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

from features.encoder import KeibaEncoder


# ── 特徴量リスト ──────────────────────────────────────────────────
FEATURE_COLS = [
    # 馬関連
    "horse_age_months", "weight_ratio", "weight_change_rate",
    "race_interval_days", "last_3f_avg_5", "finish_pos_trend",
    "win_rate_surface", "place_rate_surface", "win_rate_dist_bin",
    "race_count", "weighted_score_3",
    # エンコード済みカテゴリ
    "sex_enc", "sire_id_enc", "broodmare_sire_id_enc",
    "running_style_mode_enc",
    # 騎手関連
    "jockey_win_rate_1y", "jockey_place_rate_1y",
    "jockey_win_rate_venue", "jockey_win_rate_dist_bin",
    "jockey_win_rate_going", "jockey_interval_days",
    "jockey_horse_combo_win_rate",
    # 調教師関連
    "trainer_win_rate_1y", "trainer_place_rate_1y", "trainer_win_rate_3y",
    "trainer_win_rate_surface", "trainer_win_rate_going",
    "trainer_avg_last_3f", "trainer_jockey_combo_win_rate",
    "trainer_win_rate_grade", "trainer_win_rate_venue",
    # レース条件
    "weather_going_enc", "post_position_ratio",
    "post_bin_course_place_rate", "grade_enc",
    "field_size_scaled", "straight_length_scaled", "pace_score",
    # オッズ
    "win_odds_rank", "log_win_odds",
    "quinella_odds_min", "trifecta_odds_min",
    "odds_change_rate", "win_odds_rank_diff",
    # 相対特徴量
    "time_deviation_in_race", "handicap_diff_in_race",
    "jockey_going_affinity",
    # 馬間インタラクション
    "field_front_runner_ratio",
    "sire_surface_dist_place_rate", "broodmare_sire_going_place_rate",
    "head_to_head_win_rate",
    # その他
    "handicap_weight", "horse_weight",
]

WIN_PARAMS = {
    "objective": "binary",
    "metric": ["auc", "binary_logloss"],
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "learning_rate": 0.05,
    "n_estimators": 1000,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "scale_pos_weight": 14,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

PLACE_PARAMS = {
    **WIN_PARAMS,
    "scale_pos_weight": 4,
}


class KeibaTrainer:
    """競馬予想AIトレーナー"""

    def __init__(
        self,
        feature_path: str = "data/features/train.parquet",
        model_dir: str = "models/",
        n_splits: int = 5,
    ) -> None:
        self.feature_path = feature_path
        self.model_dir = Path(model_dir)
        self.n_splits = n_splits
        self.win_model: lgb.LGBMClassifier | None = None
        self.place_model: lgb.LGBMClassifier | None = None

    def run(self) -> dict:
        """学習パイプラインを実行してモデルを保存する"""
        logger.info("モデル学習開始")

        # データ読み込み
        df = pd.read_parquet(self.feature_path)
        df = df[df["finish_position"].notna()].copy()
        logger.info(f"学習データ: {len(df):,} rows")

        # 目的変数
        df["win_flag"]   = (df["finish_position"] == 1).astype(int)
        df["place_flag"] = (df["finish_position"] <= 3).astype(int)

        # 有効な特徴量列のみ使用
        valid_cols = [c for c in FEATURE_COLS if c in df.columns]
        missing = set(FEATURE_COLS) - set(valid_cols)
        if missing:
            logger.warning(f"欠損特徴量列 ({len(missing)}): {sorted(missing)[:10]}")

        X = df[valid_cols].fillna(0)
        y_win   = df["win_flag"]
        y_place = df["place_flag"]
        groups  = df["race_id"]

        # GroupKFold クロスバリデーション
        kf = GroupKFold(n_splits=self.n_splits)
        win_aucs, place_aucs = [], []

        for fold, (train_idx, val_idx) in enumerate(kf.split(X, y_win, groups)):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            yw_tr, yw_val = y_win.iloc[train_idx], y_win.iloc[val_idx]
            yp_tr, yp_val = y_place.iloc[train_idx], y_place.iloc[val_idx]

            # 勝利モデル
            win_model = lgb.LGBMClassifier(**WIN_PARAMS)
            win_model.fit(
                X_tr, yw_tr,
                eval_set=[(X_val, yw_val)],
                callbacks=[lgb.early_stopping(50, verbose=False),
                           lgb.log_evaluation(period=-1)],
            )
            win_auc = roc_auc_score(yw_val, win_model.predict_proba(X_val)[:, 1])
            win_aucs.append(win_auc)

            # 複勝モデル
            place_model = lgb.LGBMClassifier(**PLACE_PARAMS)
            place_model.fit(
                X_tr, yp_tr,
                eval_set=[(X_val, yp_val)],
                callbacks=[lgb.early_stopping(50, verbose=False),
                           lgb.log_evaluation(period=-1)],
            )
            place_auc = roc_auc_score(yp_val, place_model.predict_proba(X_val)[:, 1])
            place_aucs.append(place_auc)

            logger.info(
                f"Fold {fold+1}/{self.n_splits}: "
                f"win_auc={win_auc:.4f}, place_auc={place_auc:.4f}"
            )

        # 全データで最終モデルを学習
        logger.info("全データで最終モデル学習中...")
        self.win_model = lgb.LGBMClassifier(**{**WIN_PARAMS, "n_estimators": 500})
        self.win_model.fit(X, y_win)

        self.place_model = lgb.LGBMClassifier(**{**PLACE_PARAMS, "n_estimators": 500})
        self.place_model.fit(X, y_place)

        # 保存
        self.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.win_model,   self.model_dir / "lgbm_win.pkl")
        joblib.dump(self.place_model, self.model_dir / "lgbm_place.pkl")

        # バックテスト
        df["win_score"]   = self.win_model.predict_proba(X)[:, 1]
        df["place_score"] = self.place_model.predict_proba(X)[:, 1]
        bt_results = _run_backtest(df)

        # レポート
        report = {
            "trained_at": datetime.utcnow().isoformat(),
            "feature_cols": valid_cols,
            "n_train_rows": len(df),
            "cv_results": {
                "win_auc_mean":   float(np.mean(win_aucs)),
                "win_auc_std":    float(np.std(win_aucs)),
                "place_auc_mean": float(np.mean(place_aucs)),
                "place_auc_std":  float(np.std(place_aucs)),
            },
            "backtest": bt_results,
        }
        with open(self.model_dir / "training_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(
            f"学習完了 — win_auc={np.mean(win_aucs):.4f}±{np.std(win_aucs):.4f}, "
            f"place_auc={np.mean(place_aucs):.4f}±{np.std(place_aucs):.4f}"
        )
        return report


def _run_backtest(df: pd.DataFrame) -> dict:
    """各レースで予測スコア最高の馬に単勝100円購入と仮定してROIを計算"""
    results = []
    for race_id, gdf in df.groupby("race_id"):
        pred = gdf.loc[gdf["win_score"].idxmax()]
        actual_winner = gdf[gdf["finish_position"] == 1]
        if actual_winner.empty:
            continue
        hit = pred["horse_id"] == actual_winner.iloc[0]["horse_id"]
        odds = pred.get("win_odds", 10.0) or 10.0
        profit = (odds * 100 - 100) if hit else -100
        results.append({"hit": hit, "profit": profit, "investment": 100})

    if not results:
        return {"win_accuracy": 0, "win_roi": 0}

    rdf = pd.DataFrame(results)
    accuracy = rdf["hit"].mean()
    roi = rdf["profit"].sum() / rdf["investment"].sum()
    return {
        "win_accuracy":  float(accuracy),
        "win_roi":       float(roi),
        "total_races":   len(rdf),
        "total_hits":    int(rdf["hit"].sum()),
    }
