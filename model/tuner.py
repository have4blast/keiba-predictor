"""Optuna ハイパーパラメータ自動チューニング

GroupKFold(3) で Win/Place AUC を最大化するパラメータを探索する。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import lightgbm as lgb
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.model_selection import GroupKFold

if TYPE_CHECKING:
    import optuna

# train_model.py と共有する特徴量リスト（importして利用）
from model.trainer import FEATURE_COLS

WIN_TARGET   = "win_flag"
PLACE_TARGET = "place_flag"


def objective(
    trial: "optuna.Trial",
    df: pd.DataFrame,
    target: str,
    n_splits: int = 3,
) -> float:
    """Optuna の目的関数 — GroupKFold AUC 平均を返す"""
    params = {
        "objective":        "binary",
        "metric":           "auc",
        "verbosity":        -1,
        "boosting_type":    "gbdt",
        "num_leaves":       trial.suggest_int("num_leaves", 20, 300),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "min_child_samples":trial.suggest_int("min_child_samples", 5, 100),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq":     1,
        "lambda_l1":        trial.suggest_float("lambda_l1", 0.0, 10.0),
        "lambda_l2":        trial.suggest_float("lambda_l2", 0.0, 10.0),
        "n_estimators":     500,
    }

    feature_cols = [c for c in FEATURE_COLS if c in df.columns]
    target_col   = WIN_TARGET if target == "win" else PLACE_TARGET

    df_valid = df[df[target_col].notna()].copy()
    X = df_valid[feature_cols].select_dtypes(include=[np.number]).fillna(0)
    y = df_valid[target_col].astype(int)
    groups = df_valid["race_id"]

    gkf  = GroupKFold(n_splits=n_splits)
    aucs = []
    for train_idx, val_idx in gkf.split(X, y, groups):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dval   = lgb.Dataset(X_val, label=y_val, reference=dtrain)

        model = lgb.train(
            params,
            dtrain,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)],
        )
        preds = model.predict(X_val)
        from sklearn.metrics import roc_auc_score
        aucs.append(roc_auc_score(y_val, preds))

    return float(np.mean(aucs))


def tune(
    df: pd.DataFrame,
    target: str = "win",
    n_trials: int = 50,
    n_splits: int = 3,
    output_dir: str = "models",
) -> dict:
    """
    Optuna でハイパーパラメータを探索し、最良パラメータを返す。
    結果は models/tuning_report.json に保存する。
    """
    try:
        import optuna
    except ImportError:
        raise ImportError("optuna が未インストールです: pip install optuna")

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    logger.info(f"Optuna チューニング開始: target={target}, trials={n_trials}")

    study = optuna.create_study(direction="maximize")
    study.optimize(
        lambda trial: objective(trial, df, target, n_splits),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    best = study.best_trial
    logger.info(f"最良 AUC: {best.value:.4f} — params: {best.params}")

    report = {
        "target":      target,
        "best_auc":    float(best.value),
        "best_params": best.params,
        "n_trials":    n_trials,
        "n_splits":    n_splits,
        "tuned_at":    datetime.now(timezone.utc).isoformat(),
    }

    out_path = Path(output_dir) / "tuning_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"チューニング結果保存: {out_path}")

    return report
