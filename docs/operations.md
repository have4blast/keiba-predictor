# 運用手順書 — 競馬予想AI

> **対象者**: 本システムの日常運用担当者  
> **最終更新**: 2026-05-03（0003_automation 反映）

---

## 目次

1. [システム全体図](#1-システム全体図)
2. [初期セットアップ](#2-初期セットアップ)
3. [過去データ収集（初回のみ）](#3-過去データ収集初回のみ)
4. [日次運用フロー](#4-日次運用フロー)
5. [モデル再学習](#5-モデル再学習)
6. [ダッシュボード運用](#6-ダッシュボード運用)
7. [Docker コンテナ運用](#7-docker-コンテナ運用)
8. [GitHub Actions 自動化](#8-github-actions-自動化)
9. [LINE Notify 予測通知](#9-line-notify-予測通知)
10. [定期実行の自動化（cron）](#10-定期実行の自動化cron)
11. [ログ確認・監視](#11-ログ確認監視)
12. [トラブルシューティング](#12-トラブルシューティング)
13. [データ管理・メンテナンス](#13-データ管理メンテナンス)

---

## 1. システム全体図

```
[netkeiba.com]
     │
     ▼
scripts/scrape_historical.py   ← 過去レース結果（初回・定期補完）
scripts/scrape_upcoming.py     ← 翌日出走表（毎日自動）
     │
     ▼
data/keiba.db (SQLite)
     │
     ▼
scripts/build_features.py      ← 7カテゴリ・53特徴量を生成
     │
     ▼
data/features/train.parquet
     │
     ▼
scripts/train_model.py         ← LightGBM 学習（週次推奨）
     │
     ├─ models/lgbm_win.pkl
     ├─ models/lgbm_place.pkl
     ├─ models/encoder.pkl
     └─ models/training_report.json
          │
          ├─ streamlit run dashboard/app.py  ← ダッシュボード表示
          └─ scripts/notify_line.py          ← LINE Notify 通知

【GitHub Actions 自動化フロー】

daily_scrape.yml (JST 08:00 毎日)
  → scrape_upcoming + build_features → data/keiba.db + features キャッシュ更新

weekly_train.yml (JST 02:00 毎週月曜)
  → train_model + AUC 退行検知 → models/ キャッシュ更新

notify_predictions.yml (JST 09:00 毎日)
  → notify_line.py → LINE Notify 送信
```

---

## 2. 初期セットアップ

### 2-1. リポジトリのクローンと依存インストール

```bash
git clone https://github.com/have4blast/keiba-predictor.git
cd keiba-predictor

# Python 3.11+ 推奨
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2-2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して NETKEIBA_USER_AGENT・LINE_NOTIFY_TOKEN 等を設定
```

### 2-3. ディレクトリ確認

```bash
ls data/raw/ data/features/ models/ logs/
# 各ディレクトリが存在していれば OK
```

---

## 3. 過去データ収集（初回のみ）

### 推奨期間

最低 **2年分**（24ヶ月）のデータを収集することを推奨します。  
データ量が多いほどモデル精度が向上しますが、収集時間も増加します。

| 期間 | 目安収集時間 | レース数目安 |
|------|------------|------------|
| 3ヶ月 | 約30分 | ~2,000レース |
| 1年   | 約2時間 | ~8,000レース |
| 3年   | 約6時間 | ~24,000レース |

### コマンド

```bash
# 基本形
python scripts/scrape_historical.py --start 2022-01-01 --end 2024-12-31

# オプション
python scripts/scrape_historical.py \
    --start 2022-01-01 \
    --end   2024-12-31 \
    --db    data/keiba.db \
    --resume               # 中断後の再開

# 動作確認用（3ヶ月分）
python scripts/scrape_historical.py --start 2024-01-01 --end 2024-03-31
```

> **注意**: netkeiba.com への過負荷を防ぐため、ページ間に 2〜3.5 秒の遅延が入ります。  
> バックグラウンド実行を推奨します: `nohup python scripts/scrape_historical.py ... &`

### 収集後の確認

```bash
python - <<'EOF'
from sqlalchemy import create_engine, text
engine = create_engine("sqlite:///data/keiba.db")
with engine.connect() as c:
    for t in ["races","race_entries","horses","jockeys","trainers"]:
        n = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print(f"{t}: {n:,} 件")
EOF
```

---

## 4. 日次運用フロー

### 全体スケジュール（毎日）

| 時刻 | タスク | コマンド |
|------|--------|---------|
| 08:00 | 翌日出走表取得 | `scripts/scrape_upcoming.py` |
| 08:30 | 特徴量生成 | `scripts/build_features.py` |
| 09:00 | ダッシュボード確認 | `streamlit run dashboard/app.py` |

### 4-1. 翌日出走表取得

```bash
# 翌日分を取得（日付未指定時は翌日になる）
python scripts/scrape_upcoming.py

# 日付を明示する場合
python scripts/scrape_upcoming.py --date 2024-06-15

# ログ確認
tail -f logs/scrape_upcoming.log
```

### 4-2. 特徴量生成

```bash
python scripts/build_features.py

# 出力先確認
ls -lh data/features/train.parquet
```

### 4-3. 予測結果確認

```bash
streamlit run dashboard/app.py
# ブラウザで http://localhost:8501 を開く
# 「📊 予測結果」ページ → 日付・レースを選択
```

---

## 5. モデル再学習・チューニング

### 推奨タイミング

- **月次**: 毎月第1週に再学習（新しいレースデータを取り込む）
- **都度**: AUC が急落した場合（Win AUC < 0.60 を目安）
- **馬場変化時**: 梅雨入り・乾燥期など馬場状態が変わる時期

### 再学習コマンド

```bash
# 標準（学習データ全件使用）
python scripts/train_model.py

# オプション指定
python scripts/train_model.py \
    --features data/features/train.parquet \
    --models   models/ \
    --splits   5

# ログ確認
tail -f logs/train_model.log
```

### Optuna ハイパーパラメータ自動チューニング

AUC が伸び悩んでいる場合や、データ量が大幅に増えた場合に実行します。

```bash
# 勝利モデルを50トライアルで探索し、最適パラメータで自動再学習
python scripts/tune_model.py --trials 50 --target win

# 複勝モデルを100トライアルで探索（再学習はスキップ）
python scripts/tune_model.py --trials 100 --target place --no-train

# ログ確認
tail -f logs/tune_model.log
cat models/tuning_report.json
```

> **目安**: `--trials 50` で約 5〜10 分。CPU コア数が多い環境では `--trials 100` 推奨。

### 再学習後の確認

```bash
python - <<'EOF'
import json
with open("models/training_report.json") as f:
    r = json.load(f)
cv = r["cv_results"]
bt = r["backtest"]
print(f"Win AUC  : {cv['win_auc_mean']:.4f} ± {cv['win_auc_std']:.4f}")
print(f"Place AUC: {cv['place_auc_mean']:.4f} ± {cv['place_auc_std']:.4f}")
print(f"単勝的中率: {bt['win_accuracy']:.1%}")
print(f"単勝ROI  : {bt['win_roi']:.1%}")
EOF
```

### モデルのバックアップ

```bash
# 再学習前に必ずバックアップを取る
DATE=$(date +%Y%m%d)
cp -r models/ models_backup_${DATE}/
```

---

## 6. ダッシュボード運用

### 起動

```bash
# デフォルト（ポート 8501）
streamlit run dashboard/app.py

# ポート変更
streamlit run dashboard/app.py --server.port 8502

# サーバー公開（ローカルネットワーク内）
streamlit run dashboard/app.py --server.address 0.0.0.0
```

### ページ構成

| ページ | URL | 主な用途 |
|--------|-----|---------|
| ホーム | `/` | モデルサマリー確認 |
| 予測結果 | `/predictions` | 当日レース予測スコア閲覧 |
| バックテスト | `/backtest` | ROI・成績推移確認 |
| データ状況 | `/data_status` | DB件数・スクレイピング進捗 |

### キャッシュ制御

ダッシュボードは Streamlit のキャッシュ機能を使用しています。  
最新データを反映させるには:

1. `データ状況` ページの **「🔄 データ更新」** ボタンをクリック
2. または `Ctrl + Shift + R`（ブラウザのハードリフレッシュ）

---

## 7. Docker コンテナ運用

### 前提

- Docker Engine 24.0 以上
- Docker Compose v2.x 以上（`docker compose` コマンドが使えること）

### 7-1. ダッシュボードの起動

```bash
# ダッシュボードをバックグラウンドで常時起動
docker compose up -d dashboard

# ブラウザで http://localhost:8501 を開く

# ログをリアルタイム確認
docker compose logs -f dashboard

# 停止
docker compose down
```

### 7-2. 各スクリプトの実行（プロファイル指定）

```bash
# 翌日出走表取得 + 特徴量生成
docker compose --profile scrape run --rm scraper

# 過去データ一括収集（日付指定）
docker compose --profile scrape run --rm historical \
  python scripts/scrape_historical.py \
  --start 2024-01-01 --end 2024-12-31 --resume

# 特徴量生成のみ
docker compose --profile build run --rm features

# モデル学習
docker compose --profile train run --rm trainer

# データ品質検証
docker compose --profile validate run --rm validator
```

### 7-3. イメージのビルド

```bash
# 初回またはコード変更時にビルド
docker compose build

# requirements.txt を変更した場合はキャッシュなしで再ビルド
docker compose build --no-cache
```

### 7-4. 環境変数の設定（Docker 用）

コンテナは起動時に `.env` ファイルを読み込みます。

```bash
# .env に LINE_NOTIFY_TOKEN を追加
echo "LINE_NOTIFY_TOKEN=your_token_here" >> .env

# コンテナ内での確認
docker compose run --rm dashboard printenv LINE_NOTIFY_TOKEN
```

### 7-5. データ永続化

`./data`・`./models`・`./logs` はホストのディレクトリをマウントしているため、  
コンテナを削除してもデータは保持されます。

```bash
# マウントされているボリュームを確認
docker compose config --volumes
```

---

## 8. GitHub Actions 自動化

### 8-1. ワークフロー一覧

| ファイル | スケジュール | 内容 |
|---------|------------|------|
| `daily_scrape.yml` | 毎日 JST 08:00 | 翌日出走表取得 + 特徴量生成 |
| `weekly_train.yml` | 毎週月曜 JST 02:00 | モデル再学習 + AUC 退行検知 |
| `notify_predictions.yml` | 毎日 JST 09:00 | LINE Notify 予測通知送信 |

### 8-2. 初期設定（GitHub Secrets）

GitHub リポジトリ → Settings → Secrets and variables → Actions → New repository secret

| シークレット名 | 設定内容 |
|--------------|---------|
| `LINE_NOTIFY_TOKEN` | LINE Notify で発行したアクセストークン |

### 8-3. 手動実行（workflow_dispatch）

GitHub の Actions タブから手動実行できます。各ワークフローの「Run workflow」ボタンを使用するか、CLI で実行します。

```bash
# gh CLI がある場合の手動実行例
gh workflow run daily_scrape.yml

# 特定日付を指定して実行
gh workflow run daily_scrape.yml --field date=2024-06-15

# AUC 退行があっても強制でモデル更新
gh workflow run weekly_train.yml --field force=true

# 通知メッセージ内容のみ確認（送信なし）
gh workflow run notify_predictions.yml --field dry_run=true
```

### 8-4. AUC 退行検知の仕組み

`weekly_train.yml` は前回モデルとの Win AUC 差分を自動チェックします。

```
前回 Win AUC : 0.6500
今回 Win AUC : 0.6200
差分         : -0.0300
::error:: AUC 退行検知 (0.0300 > 0.02) — モデル更新をスキップします
```

- 差分 > 0.02 の場合、ワークフローが `exit 1` で失敗し、キャッシュは更新されません
- 強制更新する場合は `workflow_dispatch` で `force=true` を指定してください

### 8-5. キャッシュ管理

ワークフロー間のデータ共有に GitHub Actions キャッシュを使用しています。

| キャッシュキー | 内容 |
|-------------|------|
| `keiba-db-{run_number}` | `data/keiba.db` |
| `keiba-train-{run_number}` | `data/keiba.db` + `data/features/` + `models/` |

キャッシュは `restore-keys` パターンで最新の該当キャッシュに自動フォールバックします。  
古いキャッシュは GitHub の設定 (Settings → Actions → Caches) から手動削除できます。

### 8-6. ログ・アーティファクト

各ワークフロー実行後、ログが Artifacts として保存されます。

| アーティファクト名 | 保存期間 | 内容 |
|-----------------|---------|------|
| `daily-logs-{run_number}` | 7日間 | `logs/` ディレクトリ全体 |
| `train-logs-{run_number}` | 14日間 | `logs/` ディレクトリ全体 |
| `notify-logs-{run_number}` | 7日間 | `logs/notify_line.log` |

---

## 9. LINE Notify 予測通知

### 9-1. LINE Notify トークンの取得

1. [LINE Notify](https://notify-bot.line.me/ja/) にアクセス
2. 「マイページ」→「アクセストークンの発行（開発者向け）」
3. 通知先グループまたは「1:1でLINE Notifyから通知を受け取る」を選択
4. 発行されたトークンをコピー（**ページを閉じると再表示できません**）

### 9-2. トークンの設定

```bash
# ローカル実行用（.env に追記）
echo "LINE_NOTIFY_TOKEN=your_token_here" >> .env

# GitHub Actions 用（8-2 参照）
# リポジトリ → Settings → Secrets → LINE_NOTIFY_TOKEN
```

### 9-3. 動作確認（ドライラン）

```bash
# 送信せずメッセージ内容だけ確認
python scripts/notify_line.py --dry-run

# 特定日の予測を確認
python scripts/notify_line.py --date 2024-06-15 --dry-run --max-races 3

# 実際に送信（最大6レース）
python scripts/notify_line.py

# トークンを引数で直接指定
python scripts/notify_line.py --token YOUR_TOKEN --dry-run
```

### 9-4. 通知メッセージ形式

```
【競馬予想AI】2024-06-15 の予測

🏇 東京1R 未勝利
  🥇 本命: サンプルホース (0.8234)
  🥈 対抗: テストウマ (0.7123)
  🥉 単穴: ダミーモデル (0.6012)

🏇 東京2R 未勝利
  🥇 本命: ...
```

メッセージ長が 1,000 文字を超える場合は自動で切り捨てられます。

### 9-5. 自動通知のスケジュール

`notify_predictions.yml` が毎日 JST 09:00 に自動実行されます。  
DB にその日の出走予定レースが存在しない場合は通知をスキップします。

```
通知条件: data/keiba.db が存在し、finish_position = NULL の出走予定がある
通知なし: 出走予定レース 0 件（休日・データ未取得時）
```

---

## 10. 定期実行の自動化（cron）

> **推奨**: GitHub Actions（[セクション 8](#8-github-actions-自動化)）を使用してください。  
> ローカルサーバーで運用する場合は以下の cron 設定を参考にしてください。

以下を `crontab -e` で設定します（パスは環境に合わせて変更してください）。

```cron
# 毎日 08:00 — 翌日出走表取得
0 8 * * * cd /path/to/keiba-predictor && .venv/bin/python scripts/scrape_upcoming.py >> logs/cron.log 2>&1

# 毎日 08:30 — 特徴量生成
30 8 * * * cd /path/to/keiba-predictor && .venv/bin/python scripts/build_features.py >> logs/cron.log 2>&1

# 毎日 09:00 — LINE 予測通知
0 9 * * * cd /path/to/keiba-predictor && .venv/bin/python scripts/notify_line.py >> logs/cron.log 2>&1

# 毎週月曜 02:00 — モデル再学習（週次）
0 2 * * 1 cd /path/to/keiba-predictor && .venv/bin/python scripts/train_model.py >> logs/cron.log 2>&1

# 毎月1日 01:00 — 前月分の過去レース結果補完
0 1 1 * * cd /path/to/keiba-predictor && .venv/bin/python scripts/scrape_historical.py --start $(date -d '1 month ago' +\%Y-\%m-01) --end $(date -d 'last month' +\%Y-\%m-\%d) --resume >> logs/cron.log 2>&1
```

### systemd サービスとして常時起動（ダッシュボード）

```ini
# /etc/systemd/system/keiba-dashboard.service
[Unit]
Description=競馬予想AI Streamlit ダッシュボード
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/keiba-predictor
ExecStart=/path/to/keiba-predictor/.venv/bin/streamlit run dashboard/app.py --server.port 8501
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable keiba-dashboard
sudo systemctl start keiba-dashboard
```

---

## 11. ログ確認・監視

### ログファイル一覧

| ファイル | 内容 |
|---------|------|
| `logs/scrape_historical.log` | 過去データ収集ログ |
| `logs/scrape_upcoming.log` | 出走表収集ログ |
| `logs/build_features.log` | 特徴量生成ログ |
| `logs/train_model.log` | モデル学習ログ |
| `logs/tune_model.log` | Optuna チューニングログ |
| `logs/notify_line.log` | LINE Notify 送信ログ |
| `logs/validation.log` | データ品質検証ログ（WARNING 以上のみ） |
| `logs/cron.log` | cron 定期実行ログ |

### 確認コマンド

```bash
# 直近のエラーを確認
grep -i "error\|exception\|失敗" logs/*.log | tail -20

# スクレイピング進捗（直近50行）
tail -50 logs/scrape_upcoming.log

# モデル学習の最終結果
tail -30 logs/train_model.log

# LINE 通知の送信結果
tail -20 logs/notify_line.log
```

### 監視アラートの目安

| 指標 | 警告閾値 | 対応 |
|------|---------|------|
| Win AUC | < 0.60 | モデル再学習 |
| 単勝ROI | < -30% | 特徴量・パラメータ見直し |
| DB レース件数増加なし（3日以上） | — | スクレイパー確認 |
| `logs/scrape_upcoming.log` にエラー頻発 | — | netkeiba.com の変更確認 |
| `logs/notify_line.log` に送信失敗 | — | LINE_NOTIFY_TOKEN の有効期限確認 |
| weekly_train.yml が失敗 | — | AUC 退行の可能性（GitHub Actions のログ確認） |

---

## 12. トラブルシューティング

### Q1. スクレイパーが途中で止まる・エラーになる

**原因**: netkeiba.com の HTML 構造変更、またはアクセス制限

```bash
# 単体テスト
python - <<'EOF'
from scraper.base import RateLimitedSession
from scraper.race_list import fetch_race_ids
session = RateLimitedSession()
ids = fetch_race_ids(session, "20240101")
print(f"取得レース数: {len(ids)}")
print(ids[:3])
EOF
```

**対応**:
1. `scraper/base.py` の `try_selectors()` に新セレクタ候補を追加する
2. `scraper/race_detail.py` のフォールバックリストに新 CSS セレクタを追記する
3. User-Agent ヘッダーを変更（`scraper/base.py` の `_USER_AGENT`）
4. `--resume` オプションで再開: `python scripts/scrape_historical.py --resume`

### Q2. 特徴量生成でエラーが出る

```bash
# デバッグモードで実行
python scripts/build_features.py 2>&1 | tee /tmp/feat_debug.log
grep "ERROR\|Traceback" /tmp/feat_debug.log
```

**よくある原因と対処**:

| エラー | 原因 | 対処 |
|--------|------|------|
| `KeyError: 'last_3f_time'` | DB にカラムが存在しない | スクレイパーを再実行してデータ補完 |
| `ParserError: ... date` | 日付フォーマット不整合 | DB の `races.date` カラムを確認 |
| `MemoryError` | データ量が多すぎる | `--start`/`--end` で期間を絞り部分的に処理 |

### Q3. モデル学習の AUC が低い

**確認手順**:

```bash
# 特徴量の欠損値を確認
python - <<'EOF'
import pandas as pd
df = pd.read_parquet("data/features/train.parquet")
missing = df.isnull().sum()
missing = missing[missing > 0].sort_values(ascending=False)
print("欠損値上位10カラム:")
print(missing.head(10))
print(f"\n学習データ件数: {len(df):,} 行 / {len(df['race_id'].unique()):,} レース")
EOF
```

**対処**:
- 欠損率が高い場合: 対応するスクレイパーでデータ補完
- データ件数が少ない場合: `scrape_historical.py` で収集期間を延長

### Q4. ダッシュボードが起動しない

```bash
# ポート競合確認
lsof -i :8501

# 別ポートで起動
streamlit run dashboard/app.py --server.port 8502

# Streamlit キャッシュ削除
streamlit cache clear
```

### Q5. `models/lgbm_win.pkl` が見つからない

```bash
ls -la models/
# ファイルが存在しない場合はモデル学習を実行
python scripts/train_model.py
```

### Q6. データ品質エラーが出る

```bash
# 全テーブルを検証
python scripts/validate_data.py

# 特定レースのみ検証
python scripts/validate_data.py --race 202301010101

# 警告もエラーとして扱う厳格モード（CI 用途）
python scripts/validate_data.py --strict
```

**よくある警告と対処**:

| 警告 | 原因 | 対処 |
|------|------|------|
| `win_odds < 1.0` | スクレイプ値の誤り | 該当レースを再スクレイプ |
| `last_3f_time=NaN 高欠損率` | 旧レースデータに上がり3F なし | 許容範囲内なら無視 |
| `handicap_weight > 62.0` | 障害レース（斤量が高い） | 障害除外フィルタを検討 |

### Q7. LINE 通知が届かない

```bash
# ドライランで接続確認
python scripts/notify_line.py --dry-run

# トークンの有効性確認
curl -X GET https://notify-api.line.me/api/status \
  -H "Authorization: Bearer YOUR_TOKEN"
# {"status":200,"message":"ok"} が返れば正常
```

**確認ポイント**:
1. `LINE_NOTIFY_TOKEN` が `.env` または `secrets` に正しく設定されているか
2. トークンの有効期限（LINE Notify のマイページで確認）
3. DB に当日の出走予定レース（`finish_position IS NULL`）が存在するか
4. `logs/notify_line.log` のエラー内容を確認

### Q8. GitHub Actions が失敗する

**AUC 退行で失敗している場合**:
- Actions タブで `weekly_train.yml` の実行ログを確認
- 意図的な場合は `workflow_dispatch` で `force=true` を指定して再実行

**キャッシュが見つからない場合**:
- `restore-keys` で自動フォールバックしますが、初回または全キャッシュ削除後は DB・モデルが空になります
- ローカルで学習済みのモデルがあれば、Artifacts にアップロードするか、初回のみローカル実行を行ってください

### Q9. Docker コンテナが起動しない

```bash
# ビルドエラーの確認
docker compose build 2>&1 | tail -30

# コンテナの状態確認
docker compose ps

# ボリュームの権限確認
ls -la data/ models/ logs/
```

---

## 13. データ管理・メンテナンス

### DB のバックアップ

```bash
# 日次バックアップ（cron に追加推奨）
DATE=$(date +%Y%m%d)
cp data/keiba.db data/keiba_backup_${DATE}.db

# 古いバックアップを削除（30日以上前）
find data/ -name "keiba_backup_*.db" -mtime +30 -delete
```

### DB の最適化

SQLite は定期的に VACUUM を実行することで、ファイルサイズと読み取り速度が改善されます。

```bash
python - <<'EOF'
from sqlalchemy import create_engine, text
engine = create_engine("sqlite:///data/keiba.db")
with engine.connect() as c:
    c.execute(text("VACUUM"))
print("VACUUM 完了")
EOF
```

### Parquet ファイルの再生成

モデル再学習前は必ず最新の Parquet を再生成してください。

```bash
python scripts/build_features.py
ls -lh data/features/train.parquet
```

### モデルファイルのバージョン管理

```
models/
├── lgbm_win.pkl           ← 最新モデル
├── lgbm_place.pkl         ← 最新モデル
├── encoder.pkl            ← 最新エンコーダ
├── training_report.json   ← 学習レポート（AUC・ROI）
├── tuning_report.json     ← Optuna チューニング結果（任意）
└── archive/
    ├── 20240601/          ← 月次バックアップ
    │   ├── lgbm_win.pkl
    │   ├── lgbm_place.pkl
    │   └── training_report.json
    └── 20240701/
```

```bash
# アーカイブスクリプト例
DATE=$(date +%Y%m%d)
mkdir -p models/archive/${DATE}
cp models/lgbm_win.pkl models/lgbm_place.pkl models/encoder.pkl models/training_report.json \
   models/archive/${DATE}/
```

---

## 付録: ディレクトリ構造

```
keiba-predictor/
├── .github/workflows/
│   ├── daily_scrape.yml         ← 日次出走表取得（JST 08:00）
│   ├── weekly_train.yml         ← 週次モデル学習（月曜 02:00）
│   └── notify_predictions.yml  ← 日次 LINE 通知（JST 09:00）
├── data/
│   ├── keiba.db                 ← SQLite データベース
│   ├── raw/                     ← スクレイピング生ファイル（参照用）
│   └── features/
│       └── train.parquet        ← 学習用特徴量
├── models/
│   ├── lgbm_win.pkl             ← 勝利予測モデル
│   ├── lgbm_place.pkl           ← 複勝予測モデル
│   ├── encoder.pkl              ← カテゴリエンコーダ
│   └── training_report.json     ← 学習レポート（AUC・ROI）
├── logs/
│   ├── scrape_upcoming.log
│   ├── build_features.log
│   ├── train_model.log
│   ├── notify_line.log
│   └── cron.log
├── Dockerfile                   ← Docker イメージ定義
└── docker-compose.yml           ← マルチサービス定義
```

---

## 付録: よく使うコマンド一覧

```bash
# === データ収集 ===
python scripts/scrape_historical.py --start 2024-01-01 --end 2024-12-31 --resume
python scripts/scrape_upcoming.py
python scripts/scrape_upcoming.py --date 2024-06-15

# === 特徴量・学習 ===
python scripts/build_features.py
python scripts/train_model.py
python scripts/tune_model.py --trials 50 --target win   # Optuna チューニング

# === データ品質チェック ===
python scripts/validate_data.py                         # 全テーブル検証
python scripts/validate_data.py --race 202301010101     # 特定レースのみ
python scripts/validate_data.py --strict                # 警告もエラー扱い

# === LINE 通知 ===
python scripts/notify_line.py --dry-run                 # メッセージ内容確認
python scripts/notify_line.py --date 2024-06-15 --dry-run
python scripts/notify_line.py                           # 実際に送信

# === ダッシュボード ===
streamlit run dashboard/app.py
streamlit run dashboard/app.py --server.port 8502

# === Docker ===
docker compose up -d dashboard                          # ダッシュボード起動
docker compose --profile scrape run --rm scraper        # スクレイピング
docker compose --profile build run --rm features        # 特徴量生成
docker compose --profile train run --rm trainer         # モデル学習
docker compose --profile validate run --rm validator    # 品質検証
docker compose build --no-cache                         # イメージ再ビルド
docker compose down                                     # 全サービス停止

# === 確認・デバッグ ===
tail -f logs/scrape_upcoming.log
tail -f logs/train_model.log
tail -f logs/notify_line.log
grep -i error logs/*.log | tail -20
```
