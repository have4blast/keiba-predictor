"""予測実行モジュール（エンコーダは再フィット禁止）"""
import json
from pathlib import Path

import joblib
import pandas as pd
from loguru import logger

from features.encoder import KeibaEncoder
from model.trainer import FEATURE_COLS


class Predictor:
    """学習済みモデルを使って出走予定馬に予測スコアを付与する"""

    def __init__(self, model_dir: str = "models/") -> None:
        self.model_dir = Path(model_dir)
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self.win_model   = joblib.load(self.model_dir / "lgbm_win.pkl")
        self.place_model = joblib.load(self.model_dir / "lgbm_place.pkl")
        self.encoder     = KeibaEncoder.load(self.model_dir / "encoder.pkl")

        report_path = self.model_dir / "training_report.json"
        if report_path.exists():
            with open(report_path, encoding="utf-8") as f:
                self.report = json.load(f)
            self.feature_cols = self.report.get("feature_cols", FEATURE_COLS)
        else:
            self.feature_cols = FEATURE_COLS

        self._loaded = True
        logger.info(f"モデルロード完了 ({len(self.feature_cols)} features)")

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        df: 出走予定馬の特徴量DataFrame
        returns: 'win_score', 'place_score' 列が追加された DataFrame
        """
        self._load()

        # エンコードは再フィットしない（学習時のエンコーダをそのまま使用）
        df_enc = self.encoder.transform(df)

        valid_cols = [c for c in self.feature_cols if c in df_enc.columns]
        X = df_enc[valid_cols].fillna(0)

        df = df.copy()
        df["win_score"]   = self.win_model.predict_proba(X)[:, 1]
        df["place_score"] = self.place_model.predict_proba(X)[:, 1]

        logger.info(f"予測完了: {len(df)} 頭")
        return df.sort_values("win_score", ascending=False)
