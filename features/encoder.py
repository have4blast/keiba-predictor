"""カテゴリ変数エンコーダ（fit は学習データのみ、predict 時は再フィット禁止）"""
import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from loguru import logger


# エンコード対象カテゴリ列
CATEGORICAL_COLS = [
    "sex",
    "sire_id",
    "broodmare_sire_id",
    "surface",
    "weather_going",
    "grade",
    "distance_bin",
    "post_bin",
    "running_style_mode",
    "grade_bin",
]


class KeibaEncoder:
    """競馬予想AI 用カテゴリエンコーダ

    - fit()  : 学習データでのみ呼び出す
    - transform() : 学習・予測両方で使用
    """

    def __init__(self) -> None:
        self.encoders: dict[str, LabelEncoder] = {}
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> "KeibaEncoder":
        """学習データでエンコーダを fit する"""
        for col in CATEGORICAL_COLS:
            if col not in df.columns:
                continue
            le = LabelEncoder()
            le.fit(df[col].fillna("unknown").astype(str))
            self.encoders[col] = le
        self._fitted = True
        logger.info(f"Encoder fitted on {len(self.encoders)} columns")
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """カテゴリ列を整数にエンコードする"""
        if not self._fitted:
            raise RuntimeError("KeibaEncoder.fit() を先に呼び出してください")
        df = df.copy()
        for col, le in self.encoders.items():
            if col not in df.columns:
                df[col + "_enc"] = -1
                continue
            vals = df[col].fillna("unknown").astype(str)
            # 未知クラスは -1 にマッピング
            known = set(le.classes_)
            vals_mapped = vals.apply(lambda v: v if v in known else "unknown")
            if "unknown" not in known:
                # unknown クラスを追加
                le.classes_ = pd.Index(list(le.classes_) + ["unknown"])
            df[col + "_enc"] = le.transform(vals_mapped)
        return df

    def save(self, path: str) -> None:
        joblib.dump(self, path)
        logger.info(f"Encoder saved to {path}")

    @classmethod
    def load(cls, path: str) -> "KeibaEncoder":
        enc = joblib.load(path)
        logger.info(f"Encoder loaded from {path}")
        return enc
