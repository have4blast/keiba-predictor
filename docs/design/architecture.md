# システムアーキテクチャ設計 — 競馬予想AI

## 1. 全体アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                               │
│                                                                 │
│  netkeiba.com ──► scraper/ ──► SQLite (data/keiba.db)          │
│                     │                    │                      │
│                  base.py            models.py (ORM)            │
│               race_list.py          crud.py (upsert)           │
│               race_detail.py                                    │
│              horse_profile.py                                   │
│             jockey_profile.py                                   │
│            trainer_profile.py                                   │
│                  odds.py                                        │
│                upcoming.py                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FEATURE LAYER                               │
│                                                                 │
│  SQLite ──► features/pipeline.py ──► data/features/train.parquet│
│                    │                                            │
│            horse_features.py       (shift(1)+rolling)          │
│           jockey_features.py       リーク防止が最重要           │
│          trainer_features.py                                    │
│             race_features.py                                    │
│             odds_features.py                                    │
│         relative_features.py                                    │
│       interaction_features.py                                   │
│               encoder.py                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MODEL LAYER                                │
│                                                                 │
│  train.parquet ──► model/trainer.py ──► models/lgbm_win.pkl    │
│                         │               models/lgbm_place.pkl  │
│                  GroupKFold(5)          models/encoder.pkl      │
│                  LightGBM binary        training_report.json    │
│                  model/evaluate.py                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                            │
│                                                                 │
│  dashboard/app.py (Streamlit)                                   │
│      ├── pages/predictions.py  ← 予測スコア一覧                 │
│      ├── pages/backtest.py     ← ROI曲線・成績グラフ            │
│      └── pages/data_status.py ← DB状況・進捗                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. データフロー

### 2.1 過去データ収集フロー

```
scripts/scrape_historical.py
  --start YYYY-MM-DD --end YYYY-MM-DD [--resume]
  │
  ├── scraper/race_list.py
  │     → GET race_list.html?kaisai_date=YYYYMMDD
  │     → race_id リスト取得
  │
  ├── scraper/race_detail.py (各 race_id)
  │     → GET db.netkeiba.com/race/{race_id}/
  │     → 着順・タイム・上がり3F・ラップタイム・脚質取得
  │     → db/crud.py: upsert races, race_entries
  │
  ├── scraper/horse_profile.py (未取得 horse_id)
  │     → GET db.netkeiba.com/horse/{horse_id}/
  │     → 血統（父・母・母父）・性別・生年月日取得
  │     → db/crud.py: upsert horses
  │
  ├── scraper/jockey_profile.py (未取得 jockey_id)
  │     → GET db.netkeiba.com/jockey/{jockey_id}/
  │     → db/crud.py: upsert jockeys
  │
  ├── scraper/trainer_profile.py (未取得 trainer_id)
  │     → GET db.netkeiba.com/trainer/{trainer_id}/
  │     → db/crud.py: upsert trainers
  │
  └── scraper/odds.py (各 race_id)
        → GET api_get_odds_3wf.html?race_id={race_id}
        → 単勝・馬連・3連複オッズ取得
        → db/crud.py: upsert odds_history
```

### 2.2 特徴量生成フロー

```
scripts/build_features.py
  │
  └── features/pipeline.py
        │
        ├── SQLite JOIN クエリ（全テーブル）
        ├── race_date 昇順ソート（時系列保証）
        │
        ├── horse_features.py   → 馬関連13特徴量
        ├── jockey_features.py  → 騎手関連7特徴量
        ├── trainer_features.py → 調教師関連6特徴量
        ├── race_features.py    → レース条件7特徴量
        ├── odds_features.py    → オッズ4特徴量
        ├── relative_features.py → 相対5特徴量
        ├── interaction_features.py → 馬間5特徴量
        │
        ├── encoder.py: カテゴリ変数をラベルエンコード（学習時のみ fit）
        │
        └── → data/features/train.parquet 保存
```

### 2.3 予測フロー（翌日レース）

```
scripts/scrape_upcoming.py → SQLite (finish_position=NULL)
         │
         ▼
features/pipeline.py (predict モード)
  ※ encoder は models/encoder.pkl をロード（再フィット禁止）
         │
         ▼
model/predictor.py
  → lgbm_win.pkl: 勝率スコア
  → lgbm_place.pkl: 複勝率スコア
         │
         ▼
dashboard/pages/predictions.py
  → レース選択 → 馬スコア降順テーブル表示
```

---

## 3. モジュール依存関係

```
scraper/ ─────────────────► db/
    base.py                  models.py
    race_list.py             crud.py
    race_detail.py    ◄──────────────
    horse_profile.py
    jockey_profile.py
    trainer_profile.py
    odds.py
    upcoming.py

db/ ─────────────────────► features/
    models.py                pipeline.py
    crud.py                  horse_features.py
                             jockey_features.py
                             trainer_features.py
                             race_features.py
                             odds_features.py
                             relative_features.py
                             interaction_features.py
                             encoder.py

features/ ───────────────► model/
    pipeline.py              trainer.py
    encoder.py               predictor.py
                             evaluate.py

model/ ──────────────────► dashboard/
    predictor.py             pages/predictions.py
    evaluate.py              pages/backtest.py
db/ ─────────────────────► dashboard/
    crud.py                  pages/data_status.py
```

---

## 4. エラーハンドリング方針

| レイヤー | エラー種別 | 対応 |
|---------|----------|------|
| scraper | HTTP 429/503 | 指数バックオフでリトライ（最大3回） |
| scraper | パースエラー | loguru.warning でスキップ、続行 |
| scraper | 接続タイムアウト | loguru.error でスキップ、続行 |
| db | 書き込みエラー | loguru.error + トランザクションロールバック |
| features | NaN 値 | 0 または中央値で補完（特徴量ごとに定義） |
| model | 学習エラー | 例外を上位に伝播、CLI が終了コード1で終了 |

---

## 5. スケーラビリティ考慮

- SQLite は単一ファイル DB のため、並列書き込みは1プロセス限定
- 特徴量生成は pandas のベクトル演算を活用（ループを避ける）
- 馬間インタラクション特徴量は O(n²) のため、上位10頭（人気順）に絞る
- Parquet 保存により大規模データでも効率的なロードが可能
