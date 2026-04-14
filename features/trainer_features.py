"""調教師関連特徴量（9特徴量）"""
import pandas as pd


def _rolling_shifted(x: pd.Series, window: int) -> pd.Series:
    return x.shift(1).rolling(window, min_periods=1).mean()


def compute_trainer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["trainer_id", "date"]).reset_index(drop=True)

    if "win_flag" not in df.columns:
        df["win_flag"]   = (df["finish_position"] == 1).astype(float)
    if "place_flag" not in df.columns:
        df["place_flag"] = (df["finish_position"] <= 3).astype(float)

    # 過去1年勝率・複勝率
    df["trainer_win_rate_1y"] = (
        df.groupby("trainer_id", sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 365))
        .fillna(0)
    )
    df["trainer_place_rate_1y"] = (
        df.groupby("trainer_id", sort=False)["place_flag"]
        .transform(lambda x: _rolling_shifted(x, 365))
        .fillna(0)
    )

    # 過去3年勝率
    df["trainer_win_rate_3y"] = (
        df.groupby("trainer_id", sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 1095))
        .fillna(0)
    )

    # コース別・芝ダート別勝率
    df["trainer_win_rate_surface"] = (
        df.groupby(["trainer_id", "surface"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 50))
        .fillna(0)
    )

    # 馬場状態別勝率
    df["trainer_win_rate_going"] = (
        df.groupby(["trainer_id", "going"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 50))
        .fillna(0)
    )

    # 管理馬の平均上がり3F
    df["trainer_avg_last_3f"] = (
        df.groupby("trainer_id", sort=False)["last_3f_time"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # 騎手×調教師コンビ勝率
    df = df.sort_values(["trainer_id", "jockey_id", "date"])
    df["trainer_jockey_combo_win_rate"] = (
        df.groupby(["trainer_id", "jockey_id"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # グレード別勝率（新馬/未勝利/重賞）
    grade_bins = {
        "G1": "stakes", "G2": "stakes", "G3": "stakes", "L": "stakes",
        "新馬": "maiden", "未勝利": "maiden",
    }
    df["grade_bin"] = df["grade"].map(grade_bins).fillna("allowance")
    df["trainer_win_rate_grade"] = (
        df.groupby(["trainer_id", "grade_bin"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 30))
        .fillna(0)
    )

    # 競馬場別勝率
    df["trainer_win_rate_venue"] = (
        df.groupby(["trainer_id", "venue"], sort=False)["win_flag"]
        .transform(lambda x: _rolling_shifted(x, 50))
        .fillna(0)
    )

    return df
