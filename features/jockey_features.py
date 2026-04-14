"""騎手関連特徴量（8特徴量）"""
import pandas as pd


def _rolling_shifted(x: pd.Series, window: int) -> pd.Series:
    return x.shift(1).rolling(window, min_periods=1).mean()


def compute_jockey_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["jockey_id", "date"]).reset_index(drop=True)

    # win_flag / place_flag が未計算の場合に備えて
    if "win_flag" not in df.columns:
        df["win_flag"]   = (df["finish_position"] == 1).astype(float)
    if "place_flag" not in df.columns:
        df["place_flag"] = (df["finish_position"] <= 3).astype(float)

    # ── 騎手単体のローリング統計 ──────────────────────────────

    # 過去1年（≈365走）勝率・複勝率
    df["jockey_win_rate_1y"] = (
        df.groupby("jockey_id", sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 365))
        .fillna(0)
    )
    df["jockey_place_rate_1y"] = (
        df.groupby("jockey_id", sort=False)["place_flag"]
        .transform(lambda x: _rolling_shifted(x, 365))
        .fillna(0)
    )

    # コース別勝率（騎手×競馬場×芝ダート）
    df["jockey_win_rate_venue"] = (
        df.groupby(["jockey_id", "venue", "surface"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # 距離別勝率
    if "distance_bin" not in df.columns:
        df["distance_bin"] = pd.cut(
            df["distance"],
            bins=[0, 1200, 1400, 1800, 2200, 2600, 9999],
            labels=["short", "sprint", "mile", "intermediate", "long", "ultra"],
        ).astype(str)

    df["jockey_win_rate_dist_bin"] = (
        df.groupby(["jockey_id", "distance_bin"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # 馬場状態別勝率
    df["jockey_win_rate_going"] = (
        df.groupby(["jockey_id", "going"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # 競馬場別勝率
    df["jockey_win_rate_venue_only"] = (
        df.groupby(["jockey_id", "venue"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # 騎手競走間隔（日数）
    df = df.sort_values(["jockey_id", "date"])
    df["jockey_interval_days"] = (
        df.groupby("jockey_id", sort=False)["date"]
        .transform(lambda x: pd.to_datetime(x).diff().dt.days)
        .fillna(-1).astype(int)
    )

    # 馬×騎手コンビ勝率
    df = df.sort_values(["horse_id", "jockey_id", "date"])
    df["jockey_horse_combo_win_rate"] = (
        df.groupby(["horse_id", "jockey_id"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 20))
        .fillna(0)
    )

    return df
