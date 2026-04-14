"""馬間インタラクション特徴量（4特徴量）

計算コストの高い直接対決特徴量は上位10頭（人気順）に限定する。
"""
import pandas as pd
import numpy as np


def compute_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["race_id", "win_odds_rank"] if "win_odds_rank" in df.columns else ["race_id"])

    # ── 1. 脚質分布（レース内の先行馬比率）──────────────────────
    # 前走脚質の最頻値を使って、同一レース内の先行馬比率を計算（リーク防止済み）
    if "running_style_mode" in df.columns:
        front_map = {"逃": 1, "先": 1, "差": 0, "追": 0, "マ": 0}
        df["is_front_runner"] = df["running_style_mode"].map(front_map).fillna(0)
        df["field_front_runner_ratio"] = (
            df.groupby("race_id")["is_front_runner"]
            .transform("mean")
            .fillna(0.3)
        )
    else:
        df["field_front_runner_ratio"] = 0.3  # デフォルト値

    # ── 2. 父系×コース×距離帯 複勝率 ────────────────────────────
    if "place_flag" not in df.columns:
        df["place_flag"] = (df["finish_position"] <= 3).astype(float)
    if "sire_id" in df.columns:
        df = df.sort_values(["sire_id", "surface", "distance_bin", "date"]
                            if "distance_bin" in df.columns else ["sire_id", "date"])
        group_cols = (
            ["sire_id", "surface", "distance_bin"]
            if "distance_bin" in df.columns
            else ["sire_id"]
        )
        df["sire_surface_dist_place_rate"] = (
            df.groupby(group_cols, sort=False)["place_flag"]
            .transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())
            .fillna(0)
        )
    else:
        df["sire_surface_dist_place_rate"] = 0.0

    # ── 3. 母父×馬場状態 複勝率 ─────────────────────────────────
    if "broodmare_sire_id" in df.columns:
        df = df.sort_values(["broodmare_sire_id", "going", "date"])
        df["broodmare_sire_going_place_rate"] = (
            df.groupby(["broodmare_sire_id", "going"], sort=False)["place_flag"]
            .transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())
            .fillna(0)
        )
    else:
        df["broodmare_sire_going_place_rate"] = 0.0

    # ── 4. 直接対決勝率（上位10頭限定）───────────────────────────
    # 計算コスト軽減のため、各レースの人気上位10頭のみ対象
    df = df.sort_values(["horse_id", "date"])
    df["head_to_head_win_rate"] = _compute_h2h(df)

    return df


def _compute_h2h(df: pd.DataFrame) -> pd.Series:
    """
    直接対決勝率を計算する。
    各レースで対戦した馬ペアの過去戦績（A が B に勝った率）を求め、
    1頭あたりの平均値を特徴量とする。
    """
    result = pd.Series(0.0, index=df.index)

    # race_id ごとに同一レースの出走馬ペアを取得
    race_groups = df.groupby("race_id")

    # 過去の対戦履歴を蓄積するdict: (horse_a, horse_b) → [A_wins, total]
    h2h_record: dict[tuple, list[int]] = {}
    # race_date でソートして時系列に処理
    sorted_races = df[["race_id", "date"]].drop_duplicates().sort_values("date")

    for _, race_row in sorted_races.iterrows():
        race_id  = race_row["race_id"]
        race_df  = race_groups.get_group(race_id)

        # 上位10頭に限定（winオッズ順、なければ全頭）
        if "win_odds_rank" in race_df.columns:
            race_top = race_df.nsmallest(10, "win_odds_rank")
        else:
            race_top = race_df.head(10)

        horse_ids  = race_top["horse_id"].tolist()
        finish_pos = race_top.set_index("horse_id")["finish_position"].to_dict()

        # 過去対戦歴から平均勝率を計算（レース実施前の記録を参照）
        for horse in horse_ids:
            wins, total = 0, 0
            for opponent in horse_ids:
                if horse == opponent:
                    continue
                key = (horse, opponent)
                if key in h2h_record:
                    wins  += h2h_record[key][0]
                    total += h2h_record[key][1]
            h2h_rate = wins / total if total > 0 else 0.5
            idx = race_top[race_top["horse_id"] == horse].index
            result.loc[idx] = h2h_rate

        # レース結果を記録に追加（次回以降のレースに使用）
        for h_a in horse_ids:
            for h_b in horse_ids:
                if h_a == h_b:
                    continue
                pos_a = finish_pos.get(h_a)
                pos_b = finish_pos.get(h_b)
                if pos_a is not None and pos_b is not None:
                    key = (h_a, h_b)
                    if key not in h2h_record:
                        h2h_record[key] = [0, 0]
                    h2h_record[key][1] += 1  # total
                    if pos_a < pos_b:
                        h2h_record[key][0] += 1  # win

    return result
