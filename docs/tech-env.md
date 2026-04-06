# 技術環境ドキュメント — 競馬予想AI

## 1. 技術スタック

| レイヤー | 技術 | バージョン | 用途 |
|---------|------|----------|------|
| 言語 | Python | 3.11+ | 全体 |
| データ収集 | requests | 2.32.3 | HTTPクライアント |
| HTML解析 | beautifulsoup4 + lxml | 4.12.3 / 5.2.2 | スクレイピング |
| データ処理 | pandas | 2.2.2 | 特徴量計算 |
| 数値演算 | numpy | 1.26.4 | 配列演算 |
| DB ORM | SQLAlchemy | 2.0.30 | SQLite操作 |
| DB | SQLite | 3.x | 永続化（ファイルDB） |
| 特徴量保存 | pyarrow (Parquet) | 16.1.0 | 列指向圧縮保存 |
| ML | lightgbm | 4.3.0 | 勾配ブースティング |
| CV | scikit-learn | 1.5.0 | GroupKFold, metrics |
| 説明可能AI | shap | 0.45.1 | 特徴量重要度 |
| UI | Streamlit | 1.35.0 | Webダッシュボード |
| グラフ | plotly | 5.22.0 | インタラクティブ可視化 |
| 設定 | python-dotenv | 1.0.1 | .env 読み込み |
| CLI | click | 8.1.7 | スクリプトCLI |
| ロギング | loguru | 0.7.2 | 構造化ログ |
| 進捗表示 | tqdm | 4.66.4 | プログレスバー |
| モデル保存 | joblib | 1.4.2 | pkl シリアライズ |

---

## 2. ディレクトリ構造

```
keiba-predictor/
├── CLAUDE.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── vision.md
│   ├── tech-env.md
│   ├── requirements.md
│   ├── user-stories.md
│   ├── audit.md
│   ├── operations.md
│   └── design/
│       ├── architecture.md
│       ├── data-model.md
│       ├── features.md
│       ├── ml-pipeline.md
│       └── dashboard.md
├── scraper/
├── db/
├── features/
├── model/
├── scripts/
├── dashboard/
├── data/
│   ├── raw/
│   ├── features/
│   └── keiba.db
└── models/
```

---

## 3. スクレイピング対象

| データ | URL |
|--------|-----|
| レース一覧 | `https://race.netkeiba.com/top/race_list.html?kaisai_date=YYYYMMDD` |
| レース結果 | `https://db.netkeiba.com/race/{race_id}/` |
| 出走表 | `https://race.netkeiba.com/race/shutuba.html?race_id={race_id}` |
| 馬情報 | `https://db.netkeiba.com/horse/{horse_id}/` |
| 騎手情報 | `https://db.netkeiba.com/jockey/{jockey_id}/` |
| 調教師情報 | `https://db.netkeiba.com/trainer/{trainer_id}/` |
| オッズ (API) | `https://race.netkeiba.com/api/api_get_odds_3wf.html?race_id={race_id}` |

---

## 4. 環境変数 (.env)

```
# スクレイピング設定
SCRAPE_DELAY_MIN=2.0
SCRAPE_DELAY_MAX=3.5
USER_AGENT="Mozilla/5.0 (compatible; keiba-predictor/1.0)"

# DB設定
DATABASE_URL=sqlite:///data/keiba.db

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

---

## 5. 制約・禁止事項

- **禁止ライブラリ**: なし（要件を満たす範囲で追加可能）
- **レートリミット**: 2〜3.5秒/リクエスト必須（netkeiba利用規約遵守）
- **データリーク**: `shift(1)` なしの rolling 特徴量は使用禁止
- **モデル再フィット**: 予測時にエンコーダを再フィットしてはならない
- **SQLite**: 本番用途のため並列書き込みは1プロセスに限定

---

## 6. 開発環境セットアップ手順

```bash
# 1. 依存パッケージインストール
pip install -r requirements.txt

# 2. 環境変数設定
cp .env.example .env
# .env を編集

# 3. DBディレクトリ作成
mkdir -p data/raw data/features models logs

# 4. 動作確認
python -c "import lightgbm, streamlit, sqlalchemy; print('OK')"
```

---

## 7. デプロイ環境

- **ローカル実行**: Python 3.11 + ターミナル
- **ダッシュボード**: `streamlit run dashboard/app.py`（ポート8501）
- **スケジューラ**: cron（任意） または 手動実行
- **クラウド展開**: 将来拡張（Streamlit Cloud / EC2 等）
