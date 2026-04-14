# Stage 1-5: ワークフロー計画

## INCEPTION フェーズ完了サマリー

| ドキュメント | 場所 | 内容 |
|-----------|------|------|
| ビジョン | `docs/vision.md` | What/Why/MVP/成功基準 |
| 技術環境 | `docs/tech-env.md` | Python 3.11+ スタック、依存ライブラリ一覧 |
| 要件 | `docs/requirements.md` | FR-01〜FR-06、NFR-01〜NFR-04 |
| ユーザーストーリー | `docs/user-stories.md` | 8ストーリー（Epic 1〜4） |
| アーキテクチャ | `docs/design/architecture.md` | 4レイヤー構成・データフロー |
| DBスキーマ | `docs/design/data-model.md` | 8テーブル DDL |
| 特徴量設計 | `docs/design/features.md` | 7カテゴリ・53特徴量 |
| MLパイプライン | `docs/design/ml-pipeline.md` | LightGBM + GroupKFold |
| ダッシュボード | `docs/design/dashboard.md` | Streamlit 3ページ UI |

---

## Construction フェーズ 実行ステージ計画

| ステージ | 実行可否 | 理由 |
|---------|---------|------|
| 2-1 機能設計 | ⏭️ スキップ | `docs/design/` に詳細設計済み |
| 2-2 ドメインモデリング | ⏭️ スキップ | Python スクリプト/ML。OOP ドメイン層なし |
| 2-3 NFR 設計 | ⏭️ スキップ | `docs/requirements.md` NFRセクション完備 |
| 2-4 テスト設計 | ⏭️ スキップ | テスト戦略: Minimal（スクリプト実行確認のみ） |
| **2-5 コード生成計画** | ✅ 実行 | 10ユニットの番号付きファイル計画を提示 |
| **2-6 コード生成** | ✅ 実行 | 設計ドキュメントに基づきコードを生成 |
| **2-7 ビルド・テスト** | ✅ 実行 | `pip install` + import確認 + 型チェック |
| 3-1 デプロイ・運用計画 | ユーザー要求時 | `docs/operations.md` に記述予定 |

---

## テスト戦略

**Minimal**（テストコード自動生成なし）

理由:
- データパイプライン・スクレイピング・ML学習はリアルデータに依存するため、自動テストより手動実行確認が現実的
- ビルド確認（`pip install -r requirements.txt` + `python -c "import ..."` ）のみ実施

---

## コード生成 10ユニット（Stage 2-5 で詳細化）

| # | ユニット | 主要ファイル |
|---|---------|-----------|
| 1 | プロジェクト基盤 | `requirements.txt`, `.env.example`, `__init__.py` 群 |
| 2 | DB モデル・CRUD | `db/models.py`, `db/crud.py` |
| 3 | スクレイパー群 | `scraper/base.py`, `race_list.py`, `race_detail.py`, `horse_profile.py`, `jockey_profile.py`, `trainer_profile.py`, `odds.py`, `upcoming.py` |
| 4 | 過去データ収集スクリプト | `scripts/scrape_historical.py` |
| 5 | 翌日出走表収集スクリプト | `scripts/scrape_upcoming.py` |
| 6 | 特徴量エンジニアリング | `features/pipeline.py`, `horse_features.py`, `jockey_features.py`, `trainer_features.py`, `race_features.py`, `odds_features.py`, `relative_features.py`, `interaction_features.py`, `encoder.py` |
| 7 | 特徴量生成スクリプト | `scripts/build_features.py` |
| 8 | ML モデル | `model/trainer.py`, `predictor.py`, `evaluate.py` |
| 9 | モデル学習スクリプト | `scripts/train_model.py` |
| 10 | Streamlit ダッシュボード | `dashboard/app.py`, `pages/predictions.py`, `pages/backtest.py`, `pages/data_status.py` |
