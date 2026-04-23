"""SHAP 特徴量重要度計算

KeibaExplainer は学習済み LightGBM モデルに対して shap.TreeExplainer を適用し、
各馬ごとの予測根拠（上位特徴量と SHAP 値）を返す。
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from loguru import logger


class KeibaExplainer:
    """SHAP 値を計算して各馬の予測根拠を返すクラス"""

    def __init__(self, model_dir: str = "models") -> None:
        self.model_dir = Path(model_dir)
        self._explainers: dict[str, shap.TreeExplainer] = {}
        self._feature_cols: list[str] | None = None

    def _load(self, target: str) -> shap.TreeExplainer:
        if target in self._explainers:
            return self._explainers[target]

        model_path = self.model_dir / f"lgbm_{target}.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"モデルが見つかりません: {model_path}")

        model = joblib.load(model_path)
        explainer = shap.TreeExplainer(model)
        self._explainers[target] = explainer
        logger.info(f"SHAP Explainer ロード完了: {target}")
        return explainer

    def _get_feature_cols(self) -> list[str]:
        if self._feature_cols is not None:
            return self._feature_cols
        report_path = self.model_dir / "training_report.json"
        if report_path.exists():
            import json
            with open(report_path) as f:
                report = json.load(f)
            cols = report.get("feature_cols")
            if cols:
                self._feature_cols = cols
                return cols
        raise RuntimeError("training_report.json から特徴量リストを取得できません")

    def explain(
        self,
        df: pd.DataFrame,
        target: str = "win",
        top_n: int = 10,
    ) -> pd.DataFrame:
        """
        各行（馬）の SHAP 値を計算し、上位 top_n 特徴量名と値を付加した DataFrame を返す。

        追加カラム:
            shap_feat_1 .. shap_feat_{top_n}  — 特徴量名（影響大順）
            shap_val_1  .. shap_val_{top_n}   — SHAP 値（正=勝利寄与）
            shap_base_value                   — ベースライン予測値
        """
        explainer = self._load(target)
        feature_cols = self._get_feature_cols()

        available = [c for c in feature_cols if c in df.columns]
        if not available:
            logger.warning("SHAP 計算に必要な特徴量カラムがありません")
            return df

        X = df[available].copy()
        # 数値カラムのみに絞る（文字列カラムは除外）
        X = X.select_dtypes(include=[np.number]).fillna(0)
        used_cols = list(X.columns)

        shap_values = explainer.shap_values(X)
        # 二値分類では shap_values がリストで [neg_class, pos_class] の場合がある
        if isinstance(shap_values, list):
            sv = shap_values[1]
        else:
            sv = shap_values

        result = df.copy()
        result["shap_base_value"] = float(explainer.expected_value[1]
                                          if isinstance(explainer.expected_value, np.ndarray)
                                          else explainer.expected_value)

        for i, (row_sv, idx) in enumerate(zip(sv, df.index)):
            # 絶対値の大きい順で上位 top_n を取得
            order = np.argsort(np.abs(row_sv))[::-1][:top_n]
            for rank, col_idx in enumerate(order, 1):
                result.at[idx, f"shap_feat_{rank}"] = used_cols[col_idx]
                result.at[idx, f"shap_val_{rank}"]  = float(row_sv[col_idx])

        return result

    def shap_matrix(
        self,
        df: pd.DataFrame,
        target: str = "win",
    ) -> tuple[np.ndarray, list[str]]:
        """
        全特徴量の SHAP 値行列と特徴量名リストを返す（グローバル重要度表示用）。

        returns: (shap_matrix [n_rows x n_features], feature_names)
        """
        explainer = self._load(target)
        feature_cols = self._get_feature_cols()
        available = [c for c in feature_cols if c in df.columns]
        X = df[available].select_dtypes(include=[np.number]).fillna(0)
        used_cols = list(X.columns)

        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            sv = shap_values[1]
        else:
            sv = shap_values

        return sv, used_cols
