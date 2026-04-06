# 特徴量エンジニアリング設計 — 競馬予想AI

## 設計原則

1. **データリーク防止**: 全ローリング特徴量は `groupby().shift(1)` 後に `rolling()` を適用する
2. **計算順序**: race_date 昇順でソートしてから特徴量を計算する
3. **NaN補完**: ローリング特徴量のNaN（デビュー直後等）は0で補完する
4. **カテゴリ変数**: `encoder.py` で LabelEncoder を適用（fit は学習データのみ）

---

## カテゴリ1: 馬関連特徴量（`features/horse_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 | NaN補完 |
|---------|---|---------|----------|--------|
| `horse_age_months` | int | `(race_date - birth_date).days // 30` | 当日値OK | 0 |
| `horse_sex_enc` | int | sex → LabelEncoder | 当日値OK | -1 |
| `sire_id_enc` | int | sire_id → LabelEncoder | 当日値OK | -1 |
| `broodmare_sire_id_enc` | int | broodmare_sire_id → LabelEncoder | 当日値OK | -1 |
| `last_3f_avg_5` | float | `shift(1)+rolling(5).mean()` on `last_3f_time` | shift必須 | 0 |
| `race_interval_days` | int | `race_date - prev_race_date` (shift(1)) | shift必須 | -1 |
| `finish_pos_trend` | float | 直近3走着順の線形回帰係数（改善=負、悪化=正） | shift必須 | 0 |
| `win_rate_surface` | float | surface別 `(finish_pos==1).rolling(20)` / count | shift必須 | 0 |
| `place_rate_surface` | float | surface別 `(finish_pos<=3).rolling(20)` / count | shift必須 | 0 |
| `win_rate_dist_bin` | float | ±200m距離帯別 複勝率 rolling(20) | shift必須 | 0 |
| `weight_ratio` | float | `horse_weight / age_std_weight` (馬齢別標準体重テーブル参照) | 当日値OK | 1.0 |
| `weight_change_rate` | float | `(horse_weight - prev_horse_weight) / prev_horse_weight` | shift必須 | 0 |
| `race_count` | int | `cumcount()` per horse_id | shift必須 | 0 |
| `running_style_mode` | int | 過去5走の running_style 最頻値 → LabelEncoder | shift必須 | -1 |
| `weighted_score_3` | float | `pos[0]*0.5 + pos[1]*0.3 + pos[2]*0.2` (直近3走) | shift必須 | 0 |

**馬齢別標準体重テーブル（参考値）:**

| 馬齢 | 牡・セン (kg) | 牝 (kg) |
|------|-------------|--------|
| 2歳 | 430 | 420 |
| 3歳 | 460 | 440 |
| 4歳 | 480 | 455 |
| 5歳+ | 490 | 460 |

---

## カテゴリ2: 騎手関連特徴量（`features/jockey_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 |
|---------|---|---------|----------|
| `jockey_horse_combo_win_rate` | float | `horse_id×jockey_id` グループ `rolling(20)` 勝率 | shift必須 |
| `jockey_win_rate_1y` | float | jockey_id 365日ウィンドウ 勝率 | shift必須 |
| `jockey_place_rate_1y` | float | jockey_id 365日ウィンドウ 複勝率 | shift必須 |
| `jockey_win_rate_venue` | float | `jockey×venue` 複合グループ `rolling(30)` 勝率 | shift必須 |
| `jockey_win_rate_surface` | float | `jockey×surface` `rolling(30)` 勝率 | shift必須 |
| `jockey_win_rate_dist_bin` | float | `jockey×distance_bin` `rolling(30)` 勝率 | shift必須 |
| `jockey_interval_days` | int | jockey_id の前走からの日数差 | shift必須 |
| `jockey_win_rate_going` | float | `jockey×going` `rolling(30)` 勝率 | shift必須 |

---

## カテゴリ3: 調教師関連特徴量（`features/trainer_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 |
|---------|---|---------|----------|
| `trainer_win_rate_1y` | float | trainer_id 365日ウィンドウ 勝率 | shift必須 |
| `trainer_place_rate_1y` | float | trainer_id 365日ウィンドウ 複勝率 | shift必須 |
| `trainer_win_rate_3y` | float | trainer_id 1095日ウィンドウ 勝率 | shift必須 |
| `trainer_win_rate_venue` | float | `trainer×venue` `rolling(50)` 勝率 | shift必須 |
| `trainer_win_rate_surface` | float | `trainer×surface` `rolling(50)` 勝率 | shift必須 |
| `trainer_win_rate_going` | float | `trainer×going` `rolling(50)` 勝率 | shift必須 |
| `trainer_avg_last_3f` | float | trainer_id グループ `rolling(30)` `last_3f_time` 平均 | shift必須 |
| `trainer_jockey_combo_win_rate` | float | `trainer×jockey` `rolling(30)` 勝率 | shift必須 |
| `trainer_win_rate_grade` | float | `trainer×grade_bin` `rolling(30)` 勝率 | shift必須 |

**grade_bin 定義:**
- `maiden`: 新馬/未勝利
- `allowance`: 1勝/2勝/3勝クラス/OP
- `stakes`: G1/G2/G3/L

---

## カテゴリ4: レース条件特徴量（`features/race_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 |
|---------|---|---------|----------|
| `weather_going_enc` | int | `weather + "_" + going` → LabelEncoder | 当日値OK |
| `post_position_ratio` | float | `post_position / field_size` (0〜1) | 当日値OK |
| `post_bin_course_place_rate` | float | `post_bin(内枠/中枠/外枠)×course_id` の過去複勝率 rolling | shift必須 |
| `grade_enc` | int | grade → LabelEncoder（G1=最上位） | 当日値OK |
| `field_size_scaled` | float | `field_size / 18.0` (最大18頭で正規化) | 当日値OK |
| `straight_length_scaled` | float | `straight_length / 700.0` | 当日値OK |
| `num_curves` | int | races テーブルから直接取得 | 当日値OK |
| `pace_score` | float | 同コース過去ラップの (前半3F avg) / (後半3F avg) | shift必須 |

**post_bin 定義:**
- `inner`: post_position <= field_size * 0.33
- `middle`: post_position <= field_size * 0.67
- `outer`: それ以外

---

## カテゴリ5: オッズ・市場特徴量（`features/odds_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 |
|---------|---|---------|----------|
| `win_odds_rank` | int | `win_odds.rank(method='min')` レース内ランク | 当日値OK |
| `log_win_odds` | float | `log1p(win_odds)` | 当日値OK |
| `quinella_odds_min` | float | 当馬に関わる馬連オッズの最小値 | 当日値OK |
| `trifecta_odds_min` | float | 当馬に関わる3連複オッズの最小値 | 当日値OK |
| `odds_change_rate` | float | `(final_odds - early_odds) / early_odds` (odds_history より) | 当日値OK |

---

## カテゴリ6: 相対・統計加工特徴量（`features/relative_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 |
|---------|---|---------|----------|
| `time_deviation_in_race` | float | `race_mean_prev_time - horse_prev_avg_time` | shift必須 |
| `handicap_diff_in_race` | float | `handicap_weight - race_mean_handicap` | 当日値OK |
| `jockey_going_affinity` | float | `jockey×going` 過去複勝率（jockey_features と共有） | shift必須 |
| `win_odds_rank_diff` | float | `win_odds_rank - field_size / 2` | 当日値OK |

---

## カテゴリ7: 馬間インタラクション特徴量（`features/interaction_features.py`）

| 特徴量名 | 型 | 計算方法 | リーク防止 | 計算コスト |
|---------|---|---------|----------|----------|
| `head_to_head_win_rate` | float | 同一レース出走2馬の過去着順差 rolling 勝率（人気上位10頭限定） | shift必須 | 高 |
| `field_front_runner_ratio` | float | 同一レースの先行馬（逃/先）比率（前走脚質から） | shift必須 | 低 |
| `sire_surface_dist_place_rate` | float | `sire_id×surface×distance_bin` 過去複勝率 rolling | shift必須 | 中 |
| `broodmare_sire_going_place_rate` | float | `broodmare_sire_id×going` 過去複勝率 rolling | shift必須 | 中 |

---

## 特徴量生成順序（pipeline.py）

```python
# 1. DBから全データ読み込み
df = load_all_from_db()

# 2. 時系列ソート（必須）
df = df.sort_values(['horse_id', 'date'])

# 3. 各カテゴリ特徴量を順次計算（カテゴリ間依存なし→並列可能）
df = horse_features.compute(df)
df = jockey_features.compute(df)
df = trainer_features.compute(df)
df = race_features.compute(df)
df = odds_features.compute(df)
df = relative_features.compute(df)    # horse/jockey特徴量を参照
df = interaction_features.compute(df) # horse特徴量を参照

# 4. カテゴリエンコード
df = encoder.transform(df)  # fit は学習時のみ

# 5. 保存
df.to_parquet('data/features/train.parquet')
```

---

## 特徴量総数（概算）

| カテゴリ | 特徴量数 |
|---------|---------|
| 馬関連 | 15 |
| 騎手関連 | 8 |
| 調教師関連 | 9 |
| レース条件 | 8 |
| オッズ・市場 | 5 |
| 相対・統計加工 | 4 |
| 馬間インタラクション | 4 |
| **合計** | **53** |
