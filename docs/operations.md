# 運用手順書 — 競馬予想AI

> **対象者**: 本システムの日常運用担当者  
> **最終更新**: 2026-04-14

---

## 目次

1. [システム全体図](#1-システム全体図)
2. [初期セットアップ](#2-初期セットアップ)
3. [過去データ収集（初回のみ）](#3-過去データ収集初回のみ)
4. [日次運用フロー](#4-日次運用フロー)
5. [モデル再学習](#5-モデル再学習)
6. [ダッシュボード運用](#6-ダッシュボード運用)
7. [定期実行の自動化（cron）](#7-定期実行の自動化cron)
8. [ログ確認・監視](#8-ログ確認監視)
9. [トラブルシューティング](#9-トラブルシューティング)
10. [データ管理・メンテナンス](#10-データ管理メンテナンス)

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
          ▼
streamlit run dashboard/app.py ← ダッシュボード表示
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
# .env を編集して NETKEIBA_USER_AGENT 等を設定
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

## 5. モデル再学習

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

## 7. 定期実行の自動化（cron）

以下を `crontab -e` で設定します（パスは環境に合わせて変更してください）。

```cron
# 毎日 08:00 — 翌日出走表取得
0 8 * * * cd /path/to/keiba-predictor && .venv/bin/python scripts/scrape_upcoming.py >> logs/cron.log 2>&1

# 毎日 08:30 — 特徴量生成
30 8 * * * cd /path/to/keiba-predictor && .venv/bin/python scripts/build_features.py >> logs/cron.log 2>&1

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

## 8. ログ確認・監視

### ログファイル一覧

| ファイル | 内容 |
|---------|------|
| `logs/scrape_historical.log` | 過去データ収集ログ |
| `logs/scrape_upcoming.log` | 出走表収集ログ |
| `logs/build_features.log` | 特徴量生成ログ |
| `logs/train_model.log` | モデル学習ログ |
| `logs/cron.log` | cron 定期実行ログ |

### 確認コマンド

```bash
# 直近のエラーを確認
grep -i "error\|exception\|失敗" logs/*.log | tail -20

# スクレイピング進捗（直近50行）
tail -50 logs/scrape_upcoming.log

# モデル学習の最終結果
tail -30 logs/train_model.log
```

### 監視アラートの目安

| 指標 | 警告閾値 | 対応 |
|------|---------|------|
| Win AUC | < 0.60 | モデル再学習 |
| 単勝ROI | < -30% | 特徴量・パラメータ見直し |
| DB レース件数増加なし（3日以上） | — | スクレイパー確認 |
| `logs/scrape_upcoming.log` にエラー頻発 | — | netkeiba.com の変更確認 |

---

## 9. トラブルシューティング

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
1. `scraper/race_detail.py` の CSS セレクタを netkeiba.com の最新構造に合わせて修正
2. User-Agent ヘッダーを変更（`scraper/base.py` の `DEFAULT_HEADERS`）
3. `--resume` オプションで再開: `python scripts/scrape_historical.py --resume`

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

---

## 10. データ管理・メンテナンス

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
├── training_report.json   ← 最新レポート
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
└── logs/
    ├── scrape_historical.log
    ├── scrape_upcoming.log
    ├── build_features.log
    ├── train_model.log
    └── cron.log
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

# === ダッシュボード ===
streamlit run dashboard/app.py
streamlit run dashboard/app.py --server.port 8502

# === 確認・デバッグ ===
tail -f logs/scrape_upcoming.log
tail -f logs/train_model.log
grep -i error logs/*.log | tail -20
```
