"""オッズ・市場特徴量（5特徴量）"""
import numpy as np
import pandas as pd


def compute_odds_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 単勝人気順位（レース内ランク、昇順: 1=1番人気）
    df["win_odds_rank"] = (
        df.groupby("race_id")["win_odds"]
        .rank(method="min", ascending=True)
        .fillna(df["field_size"] / 2)
        .astype(int)
    )

    # 対数単勝オッズ（外れ値対策）
    df["log_win_odds"] = np.log1p(df["win_odds"].fillna(50))

    # 馬連オッズ最小値（当該馬が絡む最小馬連）
    # quinella_odds は JSON列: 簡略化して win_odds から推定
    df["quinella_odds_min"] = df["win_odds"].fillna(50) * 2.5  # 近似値

    # 3連複オッズ最小値（近似）
    df["trifecta_odds_min"] = df["win_odds"].fillna(50) * 10.0  # 近似値

    # オッズ変動率（odds_history から計算、データがない場合は0）
    # 実際の変動データがある場合は odds_history テーブルから JOIN して計算
    if "odds_change_rate" not in df.columns:
        df["odds_change_rate"] = 0.0

    # 人気順位差（中央値との差）
    df["win_odds_rank_diff"] = df["win_odds_rank"] - df["field_size"].fillna(14) / 2.0

    return df
