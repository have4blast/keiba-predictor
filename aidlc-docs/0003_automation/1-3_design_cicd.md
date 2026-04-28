# 設計ドキュメント — CI/CD・自動化 (B)

## 1. GitHub Actions ワークフロー設計

### 1-1. ファイル構成

```
.github/
└── workflows/
    ├── daily_scrape.yml      # 毎日 08:00 JST — 出走表取得 + 特徴量生成
    ├── weekly_train.yml      # 毎週月曜 02:00 JST — 再学習 + AUC 退行検知
    └── notify_predictions.yml# 毎日 09:00 JST — LINE 予測通知
```

### 1-2. `daily_scrape.yml` 設計

```yaml
on:
  schedule:
    - cron: '0 23 * * *'  # UTC 23:00 = JST 08:00
  workflow_dispatch:        # 手動実行も可能

jobs:
  scrape-and-features:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: キャッシュ復元 (data/ models/)
        uses: actions/cache@v4
        with:
          path: |
            data/keiba.db
            models/
          key: keiba-data-${{ github.run_number }}
          restore-keys: keiba-data-
      - run: pip install -r requirements.txt
      - run: python scripts/scrape_upcoming.py
      - run: python scripts/validate_data.py   # 品質チェック（失敗でも継続）
        continue-on-error: true
      - run: python scripts/build_features.py
      - name: キャッシュ保存
        uses: actions/cache/save@v4
        with:
          path: data/keiba.db
          key: keiba-data-${{ github.run_number }}
```

### 1-3. `weekly_train.yml` 設計 — AUC 退行検知

```yaml
steps:
  # ...省略...
  - name: 前回 AUC を保存
    run: |
      if [ -f models/training_report.json ]; then
        PREV_AUC=$(python -c "import json; r=json.load(open('models/training_report.json')); print(r['cv_results']['win_auc_mean'])")
        echo "PREV_AUC=$PREV_AUC" >> $GITHUB_ENV
      fi

  - run: python scripts/train_model.py

  - name: AUC 退行チェック
    run: |
      python - <<'EOF'
      import json, os, sys
      prev = float(os.environ.get("PREV_AUC", "0"))
      curr = json.load(open("models/training_report.json"))["cv_results"]["win_auc_mean"]
      diff = prev - curr
      print(f"前回 AUC: {prev:.4f} → 今回: {curr:.4f} (差: {diff:+.4f})")
      if diff > 0.02:
          print("::error::AUC 退行検知 — モデル更新をスキップします")
          sys.exit(1)
      EOF
```

---

## 2. Docker 設計

### 2-1. `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# デフォルトはダッシュボード
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 2-2. `docker-compose.yml`

```yaml
version: "3.9"

services:
  dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    env_file: .env
    restart: unless-stopped

  scraper:
    build: .
    command: ["python", "scripts/scrape_upcoming.py"]
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    env_file: .env
    profiles: ["scrape"]   # docker compose --profile scrape up

  trainer:
    build: .
    command: ["python", "scripts/train_model.py"]
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    env_file: .env
    profiles: ["train"]
```

---

## 3. LINE Notify 設計

### 3-1. `scripts/notify_line.py`（新規）

```python
def send_predictions(token: str, predictions: list[dict]) -> None:
    """
    各レースの上位3頭を LINE Notify で送信する。

    predictions: [
        {"venue": "東京", "race_num": 11, "race_name": "...",
         "horses": [{"name": "...", "score": 0.85}, ...]},
        ...
    ]
    """
    message = _format_message(predictions)
    resp = requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization": f"Bearer {token}"},
        data={"message": message},
        timeout=10,
    )
    resp.raise_for_status()
```

### 3-2. メッセージフォーマット

```
【競馬予想AI】2024-06-15 の予測

🏇 東京11R フェアリーS (G3)
  🥇 本命: サンライズホース (0.8512)
  🥈 対抗: ゴールデンランナー (0.7234)
  🥉 単穴: ブライトスター (0.6891)

🏇 中山9R ...
（最大5レース）
```

### 3-3. `.env` / Secrets 設定

```
LINE_NOTIFY_TOKEN=your_token_here
```

GitHub Actions では `secrets.LINE_NOTIFY_TOKEN` として参照。

---

## 実装優先度まとめ

| 実装項目 | 優先度 | ファイル |
|---------|--------|---------|
| `Dockerfile` | 高 | 新規 |
| `docker-compose.yml` | 高 | 新規 |
| `.github/workflows/daily_scrape.yml` | 高 | 新規 |
| `.github/workflows/weekly_train.yml` | 高 | 新規 |
| `scripts/notify_line.py` | 中 | 新規 |
| `.github/workflows/notify_predictions.yml` | 中 | 新規 |
| `.dockerignore` | 低 | 新規 |
