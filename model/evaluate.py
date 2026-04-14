"""バックテスト・ROI計算・成績集計"""
from pathlib import Path

import pandas as pd
import numpy as np
from loguru import logger


def run_backtest(
    df: pd.DataFrame,
    score_col: str = "win_score",
    target_col: str = "win_flag",
    odds_col: str = "win_odds",
) -> pd.DataFrame:
    """
    各レースで予測スコア最高の馬に100円投票と仮定してバックテストを行う。

    returns: レースごとの投資結果 DataFrame
    """
    records = []
    for race_id, gdf in df.groupby("race_id"):
        if gdf[score_col].isna().all():
            continue
        pred_idx   = gdf[score_col].idxmax()
        predicted  = gdf.loc[pred_idx]
        hit        = bool(predicted[target_col] == 1)
        odds       = float(predicted[odds_col]) if pd.notna(predicted.get(odds_col)) else 10.0
        profit     = (odds * 100 - 100) if hit else -100.0
        date_val   = gdf["date"].iloc[0] if "date" in gdf.columns else None
        venue_val  = gdf["venue"].iloc[0] if "venue" in gdf.columns else None

        records.append({
            "race_id":    race_id,
            "date":       date_val,
            "venue":      venue_val,
            "hit":        hit,
            "odds":       odds,
            "profit":     profit,
            "investment": 100.0,
        })

    result_df = pd.DataFrame(records)
    if result_df.empty:
        return result_df

    result_df["cumulative_profit"]     = result_df["profit"].cumsum()
    result_df["cumulative_investment"] = result_df["investment"].cumsum()
    result_df["roi_curve"] = (
        result_df["cumulative_profit"] / result_df["cumulative_investment"]
    )
    return result_df


def compute_summary(bt_df: pd.DataFrame) -> dict:
    """バックテスト結果のサマリーを返す"""
    if bt_df.empty:
        return {}
    return {
        "total_races":  len(bt_df),
        "hits":         int(bt_df["hit"].sum()),
        "accuracy":     float(bt_df["hit"].mean()),
        "total_profit": float(bt_df["profit"].sum()),
        "roi":          float(bt_df["profit"].sum() / bt_df["investment"].sum()),
    }


def compute_monthly_stats(bt_df: pd.DataFrame) -> pd.DataFrame:
    """月別成績集計"""
    if bt_df.empty or "date" not in bt_df.columns:
        return pd.DataFrame()
    bt_df = bt_df.copy()
    bt_df["month"] = pd.to_datetime(bt_df["date"]).dt.to_period("M").astype(str)
    monthly = bt_df.groupby("month").agg(
        races=("hit", "count"),
        hits=("hit", "sum"),
        profit=("profit", "sum"),
        investment=("investment", "sum"),
    ).reset_index()
    monthly["accuracy"] = monthly["hits"] / monthly["races"]
    monthly["roi"]      = monthly["profit"] / monthly["investment"]
    return monthly


def compute_venue_stats(bt_df: pd.DataFrame) -> pd.DataFrame:
    """競馬場別成績集計"""
    if bt_df.empty or "venue" not in bt_df.columns:
        return pd.DataFrame()
    venue = bt_df.groupby("venue").agg(
        races=("hit", "count"),
        hits=("hit", "sum"),
        profit=("profit", "sum"),
        investment=("investment", "sum"),
    ).reset_index()
    venue["accuracy"] = venue["hits"] / venue["races"]
    venue["roi"]      = venue["profit"] / venue["investment"]
    return venue.sort_values("roi", ascending=False)
