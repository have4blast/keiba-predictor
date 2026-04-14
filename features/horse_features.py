"""馬関連特徴量（15特徴量）
全ローリング特徴量に shift(1) を適用してデータリークを防止する。
"""
import json
import numpy as np
import pandas as pd


# 馬齢別標準体重（参考値）
_STD_WEIGHT = {2: 425, 3: 450, 4: 468, 5: 475}


def _std_weight(age_years: float) -> float:
    age = int(age_years)
    return _STD_WEIGHT.get(age, 480)


def _rolling_shifted(x: pd.Series, window: int, agg: str = "mean") -> pd.Series:
    """shift(1) → rolling(window) → agg でリーク防止"""
    shifted = x.shift(1)
    r = shifted.rolling(window, min_periods=1)
    if agg == "mean":
        return r.mean()
    elif agg == "sum":
        return r.sum()
    elif agg == "std":
        return r.std()
    return r.mean()


def compute_horse_features(df: pd.DataFrame) -> pd.DataFrame:
    """馬関連特徴量を計算して df に追加する"""
    df = df.copy()
    df = df.sort_values(["horse_id", "date"]).reset_index(drop=True)

    g = df.groupby("horse_id", sort=False)

    # ── 静的特徴量（リーク不要）───────────────────────────
    # 馬齢（月数）
    df["horse_age_months"] = (
        pd.to_datetime(df["date"]) - pd.to_datetime(df["birth_date"])
    ).dt.days.div(30.44).fillna(0).astype(int)

    # 性別エンコード（encoder.py で LabelEncode されるため文字列のまま残す）
    # horse_sex_enc は encoder.py が処理

    # 父・母父 ID は encoder.py でエンコード

    # 馬体重比率
    df["horse_age_years"] = df["horse_age_months"] / 12.0
    df["weight_ratio"] = df.apply(
        lambda r: (r["horse_weight"] / _std_weight(r["horse_age_years"]))
        if pd.notna(r["horse_weight"]) else 1.0,
        axis=1,
    )

    # 馬体重増減率（前走との比較、前走情報はshift済み）
    df["weight_change_rate"] = g["horse_weight"].transform(
        lambda x: x.diff() / x.shift(1)
    ).fillna(0)

    # 競走間隔（日数）※ diff() は自然にprev_dateを参照する
    df["race_interval_days"] = g["date"].transform(
        lambda x: pd.to_datetime(x).diff().dt.days
    ).fillna(-1).astype(int)

    # ── ローリング特徴量（shift(1) 必須）─────────────────

    # 上がり3F平均（直近5走）
    df["last_3f_avg_5"] = g["last_3f_time"].transform(
        lambda x: _rolling_shifted(x, 5)
    ).fillna(0)

    # 勝率・複勝率（芝/ダート別、直近20走）
    df["win_flag"]   = (df["finish_position"] == 1).astype(float)
    df["place_flag"] = (df["finish_position"] <= 3).astype(float)

    df["win_rate_surface"] = (
        df.groupby(["horse_id", "surface"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 20))
        .fillna(0)
    )
    df["place_rate_surface"] = (
        df.groupby(["horse_id", "surface"], sort=False)["place_flag"]
        .transform(lambda x: _rolling_shifted(x, 20))
        .fillna(0)
    )

    # 距離帯別複勝率（距離ビン±200m近似）
    df["distance_bin"] = pd.cut(
        df["distance"],
        bins=[0, 1200, 1400, 1800, 2200, 2600, 9999],
        labels=["short", "sprint", "mile", "intermediate", "long", "ultra"],
    ).astype(str)

    df["win_rate_dist_bin"] = (
        df.groupby(["horse_id", "distance_bin"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 20))
        .fillna(0)
    )

    # レース経験数（累計、現在レースを除く）
    df["race_count"] = g["race_id"].transform(
        lambda x: pd.Series(range(len(x)), index=x.index)
    )

    # 脚質（過去5走最頻値）
    df["running_style_mode"] = g["running_style"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=1).apply(
            lambda vals: pd.Series(vals).mode().iloc[0] if len(vals) > 0 else np.nan,
            raw=False,
        )
    )

    # 直近着順推移（線形傾斜：改善=負、悪化=正）
    def _pos_slope(x: pd.Series) -> pd.Series:
        shifted = x.shift(1)
        result = []
        for i in range(len(shifted)):
            window = shifted.iloc[max(0, i - 2): i + 1].dropna()
            if len(window) < 2:
                result.append(0.0)
            else:
                slope = np.polyfit(range(len(window)), window.values, 1)[0]
                result.append(slope)
        return pd.Series(result, index=x.index)

    df["finish_pos_trend"] = g["finish_position"].transform(_pos_slope).fillna(0)

    # 過去3走加重スコア（w=[0.5, 0.3, 0.2]）
    def _weighted_score(x: pd.Series) -> pd.Series:
        shifted = x.shift(1)
        result = []
        for i in range(len(shifted)):
            vals = shifted.iloc[max(0, i - 2): i + 1].dropna().values[::-1]
            weights = [0.5, 0.3, 0.2][: len(vals)]
            score = np.dot(vals, weights) / sum(weights) if weights else 0.0
            result.append(score)
        return pd.Series(result, index=x.index)

    df["weighted_score_3"] = g["finish_position"].transform(_weighted_score).fillna(0)

    return df
