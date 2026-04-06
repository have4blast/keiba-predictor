# 監査ログ — 競馬予想AI

AI-DLC 方式に基づき、全ての重要な設計決定と作業記録をここに記録する。

---

## 2026-04-06T07:00:00Z — PHASE 0: プロジェクト開始

**決定事項:**
- リポジトリ: `have4blast/keiba-predictor`
- 開発ブランチ: `claude/horse-racing-prediction-ai-GE5ue`
- 開発方式: AWS AI-DLC (INCEPTION → CONSTRUCTION → OPERATIONS)
- `CLAUDE.md` を作成し AI-DLC ルールを記述

---

## 2026-04-06T07:05:00Z — PHASE 1: INCEPTION ドキュメント作成開始

**作成ドキュメント:**
1. `docs/vision.md` — プロジェクトビジョン・MVPスコープ定義
2. `docs/tech-env.md` — 技術スタック・環境設定定義
3. `docs/requirements.md` — 機能要件(FR-01〜FR-06)・非機能要件(NFR-01〜NFR-04)
4. `docs/user-stories.md` — 8ユーザーストーリー（Epic 1〜4）
5. `docs/design/architecture.md` — システムアーキテクチャ（4レイヤー構成）
6. `docs/design/data-model.md` — DBスキーマ（8テーブル）
7. `docs/design/features.md` — 特徴量設計（7カテゴリ・計53特徴量）
8. `docs/design/ml-pipeline.md` — LightGBM 学習・予測パイプライン設計
9. `docs/design/dashboard.md` — Streamlit 3ページ構成UI設計

**主要設計決定:**
- DB: SQLite（単一ファイル、並列書き込み1プロセス限定）
- ML: LightGBM binary × 2（勝利・複勝）、GroupKFold(5)
- 特徴量: 7カテゴリ計53特徴量、全ローリング特徴量に shift(1) 適用
- UI: Streamlit 3ページ（予測・バックテスト・データ状況）
- 馬間インタラクション: O(n²) 回避のため上位10頭限定

---

## PHASE 1 承認チェックポイント

**ステータス**: INCEPTION ドキュメント完成 — ユーザー承認待ち

CONSTRUCTION フェーズへ移行する前に、以下のドキュメントのレビューと承認をお願いします:
- [ ] `docs/vision.md`
- [ ] `docs/tech-env.md`
- [ ] `docs/requirements.md`
- [ ] `docs/user-stories.md`
- [ ] `docs/design/architecture.md`
- [ ] `docs/design/data-model.md`
- [ ] `docs/design/features.md`
- [ ] `docs/design/ml-pipeline.md`
- [ ] `docs/design/dashboard.md`
