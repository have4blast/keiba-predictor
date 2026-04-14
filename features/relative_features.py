"""相対・統計加工特徴量（4特徴量）"""
import pandas as pd


def compute_relative_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["horse_id", "date"])

    # 過去平均タイム（shift済み）
    df["horse_prev_avg_time"] = (
        df.groupby("horse_id", sort=False)["time"]
        .transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
        .fillna(0)
    )

    # レース内タイム偏差（同一レース内での相対評価）
    race_mean_time = df.groupby("race_id")["horse_prev_avg_time"].transform("mean")
    df["time_deviation_in_race"] = race_mean_time - df["horse_prev_avg_time"]

    # レース内斤量差（当馬斤量 - レース平均斤量）
    race_mean_handicap = df.groupby("race_id")["handicap_weight"].transform("mean")
    df["handicap_diff_in_race"] = df["handicap_weight"].fillna(55) - race_mean_handicap.fillna(55)

    # 騎手×馬場相性スコア（jockey_features で計算済みの jockey_win_rate_going を再利用）
    if "jockey_win_rate_going" in df.columns:
        df["jockey_going_affinity"] = df["jockey_win_rate_going"]
    else:
        df["jockey_going_affinity"] = 0.0

    # 人気順位差（odds_features で計算済み、再掲）
    if "win_odds_rank_diff" not in df.columns:
        df["win_odds_rank_diff"] = 0.0

    return df
