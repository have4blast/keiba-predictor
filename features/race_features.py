"""レース条件特徴量（8特徴量）"""
import json
import numpy as np
import pandas as pd


def compute_race_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 天候×馬場状態の複合（encoder.py でエンコード）
    df["weather_going"] = (
        df["weather"].fillna("不明") + "_" + df["going"].fillna("不明")
    )

    # 相対枠番位置（0〜1）
    df["post_position_ratio"] = (
        df["post_position"] / df["field_size"].replace(0, 1)
    ).fillna(0.5)

    # 内/中/外 枠ビン
    def _post_bin(row) -> str:
        if pd.isna(row["post_position"]) or pd.isna(row["field_size"]) or row["field_size"] == 0:
            return "unknown"
        ratio = row["post_position"] / row["field_size"]
        if ratio <= 0.33:
            return "inner"
        elif ratio <= 0.67:
            return "middle"
        else:
            return "outer"

    df["post_bin"] = df.apply(_post_bin, axis=1)

    # 枠番×コース別複勝率（リーク防止: shift済み）
    if "place_flag" not in df.columns:
        df["place_flag"] = (df["finish_position"] <= 3).astype(float)

    df = df.sort_values(["horse_id", "date"])
    df["post_bin_course_place_rate"] = (
        df.groupby(["post_bin", "venue", "surface"], sort=False)["place_flag"]
        .transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())
        .fillna(0)
    )

    # グレードはカテゴリ → encoder.py でエンコード

    # 出走頭数（正規化）
    df["field_size_scaled"] = df["field_size"].fillna(14) / 18.0

    # 直線長さ（正規化）
    df["straight_length_scaled"] = (
        df["straight_length"].fillna(300) / 700.0
    )

    # ペーススコア（前半ラップ/後半ラップ比率）
    def _pace_score(lap_json: str, distance: int) -> float:
        if not lap_json:
            return 1.0
        try:
            laps = json.loads(lap_json)
        except Exception:
            return 1.0
        if len(laps) < 4:
            return 1.0
        mid = len(laps) // 2
        front = sum(laps[:mid]) / max(mid, 1)
        back  = sum(laps[mid:]) / max(len(laps) - mid, 1)
        return front / back if back > 0 else 1.0

    df["pace_score"] = df.apply(
        lambda r: _pace_score(r.get("lap_times", ""), r.get("distance", 0)), axis=1
    )

    return df
