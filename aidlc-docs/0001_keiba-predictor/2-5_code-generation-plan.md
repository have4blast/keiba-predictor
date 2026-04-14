# Stage 2-5: コード生成計画

テスト戦略: **Minimal**（実装コードのみ生成）  
生成ファイル総数: **47ファイル**

---

## ユニット 1: プロジェクト基盤

- [x] 1-1. `requirements.txt` — 依存ライブラリ一覧（16パッケージ）
- [x] 1-2. `.env.example` — 環境変数テンプレート
- [x] 1-3. `.gitignore` — Python/データファイル除外設定
- [x] 1-4. `data/raw/.gitkeep` — rawデータディレクトリ保持
- [x] 1-5. `data/features/.gitkeep` — 特徴量ディレクトリ保持
- [x] 1-6. `models/.gitkeep` — モデル保存ディレクトリ保持
- [x] 1-7. `logs/.gitkeep` — ログディレクトリ保持

## ユニット 2: DB モデル・CRUD

- [x] 2-1. `db/__init__.py` — パッケージ初期化（エンジン生成・セッション）
- [x] 2-2. `db/models.py` — SQLAlchemy ORM定義（races, race_entries, horses, jockeys, trainers, stallions, odds_history, courses）
- [x] 2-3. `db/crud.py` — upsert操作（insert_or_update per テーブル）

## ユニット 3: スクレイパー群

- [x] 3-1. `scraper/__init__.py` — パッケージ初期化
- [x] 3-2. `scraper/base.py` — レートリミット付きHTTPセッション（`time.sleep(random.uniform(2.0, 3.5))`、User-Agent、リトライ）
- [x] 3-3. `scraper/race_list.py` — 開催日ごとのレースID一覧取得
- [x] 3-4. `scraper/race_detail.py` — レース結果詳細（着順・タイム・上がり3F・ラップ・脚質・コーナー通過順）
- [x] 3-5. `scraper/horse_profile.py` — 馬プロフィール（血統・性別・生年月日）
- [x] 3-6. `scraper/jockey_profile.py` — 騎手プロフィール
- [x] 3-7. `scraper/trainer_profile.py` — 調教師プロフィール
- [x] 3-8. `scraper/odds.py` — オッズ取得（単勝・馬連・3連複・変動履歴）
- [x] 3-9. `scraper/upcoming.py` — 翌日出走表（shutuba）

## ユニット 4: 過去データ一括収集スクリプト

- [x] 4-1. `scripts/scrape_historical.py` — `--start`/`--end`/`--resume` オプション付きCLI

## ユニット 5: 翌日出走表収集スクリプト

- [x] 5-1. `scripts/scrape_upcoming.py` — 翌日全レース出走表取得CLI

## ユニット 6: 特徴量エンジニアリング

- [x] 6-1. `features/__init__.py` — パッケージ初期化
- [x] 6-2. `features/pipeline.py` — `FeaturePipeline`（DB読み込み→時系列ソート→全特徴量計算→Parquet保存）
- [x] 6-3. `features/horse_features.py` — 馬関連15特徴量（馬齢・血統・脚質・競走間隔・体重比率等）
- [x] 6-4. `features/jockey_features.py` — 騎手関連8特徴量（コンビ成績・コース/距離/馬場適性等）
- [x] 6-5. `features/trainer_features.py` — 調教師関連9特徴量（勝率・コース・グレード適性等）
- [x] 6-6. `features/race_features.py` — レース条件8特徴量（天候×馬場・枠番・グレード・ペース予測等）
- [x] 6-7. `features/odds_features.py` — オッズ5特徴量（人気順位・対数・変動率等）
- [x] 6-8. `features/relative_features.py` — 相対4特徴量（タイム偏差・斤量差・騎手×馬場相性等）
- [x] 6-9. `features/interaction_features.py` — 馬間4特徴量（直接対決・脚質分布・血統×コース等）
- [x] 6-10. `features/encoder.py` — カテゴリ変数エンコーダ（fit/transform分離）

## ユニット 7: 特徴量生成スクリプト

- [x] 7-1. `scripts/build_features.py` — `FeaturePipeline` を呼び出しParquet保存するCLI

## ユニット 8: ML モデル

- [x] 8-1. `model/__init__.py` — パッケージ初期化
- [x] 8-2. `model/trainer.py` — `GroupKFold(5)` + LightGBM 勝利/複勝 学習（`scale_pos_weight`・early stopping）
- [x] 8-3. `model/predictor.py` — `Predictor`クラス（pkl読み込み・特徴量変換・スコア付与）
- [x] 8-4. `model/evaluate.py` — バックテスト・ROI計算・月別成績集計

## ユニット 9: モデル学習スクリプト

- [x] 9-1. `scripts/train_model.py` — `trainer.py` を呼び出し pkl + training_report.json を生成するCLI

## ユニット 10: Streamlit ダッシュボード

- [x] 10-1. `dashboard/__init__.py` — パッケージ初期化
- [x] 10-2. `dashboard/app.py` — エントリポイント（`st.set_page_config`・キャッシュ設定）
- [x] 10-3. `dashboard/pages/__init__.py` — パッケージ初期化
- [x] 10-4. `dashboard/pages/predictions.py` — 予測結果ページ（レース選択・出走馬スコアテーブル・スコア棒グラフ）
- [x] 10-5. `dashboard/pages/backtest.py` — バックテストページ（ROI曲線・月別成績・競馬場別成績）
- [x] 10-6. `dashboard/pages/data_status.py` — データ状況ページ（DB件数・最終更新・スクレイピング管理）

---

## 生成ファイル総数サマリー

| ユニット | ファイル数 |
|---------|---------|
| 1 プロジェクト基盤 | 7 |
| 2 DB | 3 |
| 3 スクレイパー | 9 |
| 4 過去収集スクリプト | 1 |
| 5 翌日収集スクリプト | 1 |
| 6 特徴量 | 10 |
| 7 特徴量スクリプト | 1 |
| 8 ML モデル | 4 |
| 9 学習スクリプト | 1 |
| 10 ダッシュボード | 6 |
| **合計** | **43** |
