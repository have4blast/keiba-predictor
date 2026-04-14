# AI-DLC ワークフロー状態管理

- **プロジェクト**: 競馬予想AI (keiba-predictor)
- **feature-name**: `0001_keiba-predictor`
- **出力先**: `aidlc-docs/0001_keiba-predictor/`
- **depth**: `standard`
- **テスト戦略**: Minimal（Python スクリプト / ML パイプライン）
- **最終更新**: 2026-04-14 (Stage 3-1 完了 — OPERATIONS フェーズ完了)

---

## ステージ進捗

| ステージ | 名前 | ステータス | 備考 |
|---------|------|---------|------|
| 1-1 | ワークスペース検出 | ✅ 完了 | グリーンフィールド。Python/Streamlit/LightGBM スタック確定 |
| 1-2 | 要件分析・技術スタック選定 | ✅ 完了 | `docs/requirements.md` + `docs/tech-env.md` 作成済み |
| 1-3 | ユーザーストーリー | ✅ 完了 | `docs/user-stories.md` 作成済み（8ストーリー） |
| 1-4 | アプリケーション設計 | ✅ 完了 | `docs/design/` 配下5ドキュメント作成済み |
| 1-5 | ワークフロー計画 | ✅ 完了 | `1-5_execution-plan.md` 参照 |
| 2-1 | 機能設計 | ⏭️ スキップ | 詳細設計は `docs/design/` で完了済み |
| 2-2 | ドメインモデリング | ⏭️ スキップ | Python スクリプト/ML プロジェクト。OOP ドメイン層なし |
| 2-3 | NFR 設計 | ⏭️ スキップ | `docs/requirements.md` の NFR セクションで対応済み |
| 2-4 | テスト設計 | ⏭️ スキップ | テスト戦略: Minimal |
| 2-5 | コード生成計画 | ✅ 完了 | `2-5_code-generation-plan.md` 参照 |
| 2-6 | コード生成 | ✅ 完了 | 全43ファイル生成済み（ユニット1〜10）|
| 2-7 | ビルド・テスト | ✅ 完了 | 全モジュールインポート・構文チェック・機能テスト OK |
| 3-1 | デプロイ・運用計画 | ✅ 完了 | `docs/operations.md` 作成（日次フロー・cron・障害対応） |

---

## プロジェクト概要（ワークスペース検出結果）

- **種別**: グリーンフィールド（新規構築）
- **言語**: Python 3.11+
- **主要ライブラリ**: LightGBM, Streamlit, SQLAlchemy, pandas, scikit-learn, SHAP
- **DB**: SQLite（`data/keiba.db`）
- **データソース**: netkeiba.com（スクレイピング）
- **特徴量**: 7カテゴリ・53特徴量
- **既存コード**: なし（INCEPTION ドキュメントのみ）
