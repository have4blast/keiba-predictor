# CLAUDE.md — 競馬予想AI (keiba-predictor)

## 開発プロセス: AI-DLC (AI-Driven Development Life Cycle)

このプロジェクトは AWS AI-DLC 方式で開発する。以下のルールを常に遵守すること。

---

## コア原則

1. **ドキュメント先行**: コードを生成する前に必ず設計ドキュメント（`docs/design/`）を確定し承認を得る
2. **承認ゲート**: INCEPTION → CONSTRUCTION → OPERATIONS の各フェーズ移行前にユーザー承認を得る
3. **ソースオブトゥルース**: 設計ドキュメントがソースオブトゥルース。コードを直接編集せず、先にドキュメントを更新してからコードを再生成する
4. **監査証跡**: 全ての設計決定を `docs/audit.md` に ISO タイムスタンプ付きで記録する

---

## フェーズ構成

### INCEPTION PHASE（完了後に承認を得ること）
- `docs/vision.md` — プロジェクトビジョン・MVPスコープ
- `docs/tech-env.md` — 技術環境・制約
- `docs/requirements.md` — 機能・非機能要件
- `docs/user-stories.md` — ユーザーストーリー
- `docs/design/architecture.md` — システムアーキテクチャ
- `docs/design/data-model.md` — DBスキーマ設計
- `docs/design/features.md` — 特徴量エンジニアリング設計（7カテゴリ）
- `docs/design/ml-pipeline.md` — ML学習・予測パイプライン設計
- `docs/design/dashboard.md` — Streamlitダッシュボード設計

### CONSTRUCTION PHASE（各ユニット前に番号付きファイル計画を提示し承認を得ること）
実装順:
1. プロジェクト基盤
2. `db/` — DBモデル・CRUD
3. `scraper/` — スクレイパー群
4. `scripts/scrape_historical.py`
5. `scripts/scrape_upcoming.py`
6. `features/` — 特徴量エンジニアリング
7. `scripts/build_features.py`
8. `model/` — ML モデル
9. `scripts/train_model.py`
10. `dashboard/` — Streamlit UI

### OPERATIONS PHASE
- `docs/operations.md` — 運用手順

---

## コーディング規約

- Python 3.11+
- 型ヒントを付ける（関数シグネチャのみ、内部変数は不要）
- データリーク防止: 全ローリング特徴量に `shift(1)` を適用
- スクレイピング: `time.sleep(random.uniform(2.0, 3.5))` でレートリミット遵守
- ログ: `loguru` を使用
- DB操作: SQLAlchemy ORM + upsert
- 特徴量: Parquet形式で保存

---

## 重要ファイルパス

| 目的 | パス |
|------|------|
| ビジョン | `docs/vision.md` |
| 技術環境 | `docs/tech-env.md` |
| 要件 | `docs/requirements.md` |
| アーキテクチャ設計 | `docs/design/architecture.md` |
| DBスキーマ設計 | `docs/design/data-model.md` |
| 特徴量設計 | `docs/design/features.md` |
| ML設計 | `docs/design/ml-pipeline.md` |
| UI設計 | `docs/design/dashboard.md` |
| 監査ログ | `docs/audit.md` |
