# 設計ドキュメント — スクレイパー堅牢化 (C)

## 1. フォールバックパーサー設計

### 対象ファイル: `scraper/base.py` 拡張

現状は単一 CSS セレクタで解析している。HTML 構造変更時に即座に失敗する。

**変更方針**: `try_selectors()` ヘルパーを追加し、候補セレクタを順番に試みる。

```python
def try_selectors(soup: BeautifulSoup, selectors: list[str]) -> Tag | None:
    """複数セレクタを順に試し、最初にヒットした要素を返す。全て失敗したら None"""
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            logger.debug(f"セレクタ使用: {sel}")
            return el
    logger.warning(f"全セレクタ失敗: {selectors}")
    return None
```

### 各スクレイパーへの適用例（`scraper/race_detail.py`）

```python
# 変更前
table = soup.select_one("table.race_table_01")

# 変更後
table = try_selectors(soup, [
    "table.race_table_01",   # 旧セレクタ
    "table.RaceTable01",     # 別パターン
    "div#result_table table",# フォールバック
])
if table is None:
    logger.error(f"レース結果テーブル取得失敗: {race_id}")
    return {}
```

適用対象スクレイパー:
- `race_detail.py` — レース結果テーブル・タイム・上がり3F
- `race_list.py` — レースIDリスト
- `horse_profile.py` — 馬プロフィール・血統テーブル

---

## 2. データ品質バリデーター設計

### 2-1. `db/validator.py`（新規）

```python
class DataValidator:
    RULES = {
        "race_entries": {
            "finish_position": {"min": 1, "max": 28, "null_ok": True},
            "win_odds":        {"min": 1.0, "max": 9999.9, "null_ok": True},
            "last_3f_time":    {"min": 30.0, "max": 45.0, "null_ok": True},
            "horse_weight":    {"min": 350, "max": 650, "null_ok": True},
            "handicap_weight": {"min": 48.0, "max": 62.0, "null_ok": True},
        },
        "races": {
            "distance": {"min": 800, "max": 4000, "null_ok": False},
            "field_size": {"min": 1, "max": 28, "null_ok": True},
        },
    }

    def validate(self, session) -> ValidationReport
        # 各テーブル・カラムに対してルールチェック
        # 欠損率・外れ値件数を集計
        # ValidationReport(errors, warnings, ok_count) を返す

    def validate_race(self, session, race_id: str) -> ValidationReport
        # 特定レースのみ検証（スクレイプ直後の即時チェック用）
```

`ValidationReport` 構造:
```python
@dataclass
class ValidationReport:
    errors:    list[str]   # 即時対応が必要な問題
    warnings:  list[str]   # 注意すべき問題
    ok_count:  int
    checked_at: datetime
```

### 2-2. `scripts/validate_data.py`（新規）

```
python scripts/validate_data.py
  → 全テーブルを検証してコンソール出力 + logs/validation.log
  → exit code 0 (警告のみ) / 1 (エラーあり)
```

出力例:
```
=== データ品質レポート ===
  races        : 600件チェック OK
  race_entries : 7,683件中 12件 警告
    WARNING: win_odds=0.8 (下限 1.0 未満) — race_id=202301010101, horse_id=H00042
    WARNING: last_3f_time=NaN — race_entries 23件 (0.3%)
  horses       : 1,200件チェック OK
```

---

## 3. 調教タイムスクレイパー設計

### 3-1. `scraper/training_time.py`（新規）

```
取得元: https://db.netkeiba.com/horse/yyyynnnnnnn/  の「調教」タブ
```

```python
def fetch_training_times(session: RateLimitedSession, horse_id: str) -> list[dict]:
    # 戻り値: [{"date": "2023-01-07", "course": "坂路", "time": 52.3, "last_f": 12.1}, ...]
```

### 3-2. DB スキーマ追加: `training_times` テーブル

```sql
training_times:
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    horse_id    TEXT NOT NULL (FK → horses)
    date        DATE NOT NULL
    course      TEXT   -- 坂路/ウッド/芝/ダート/プール
    total_time  FLOAT  -- 全体タイム（秒）
    last_f_time FLOAT  -- 最終F（秒）
    gear        TEXT   -- 強め/馬なり/一杯
    created_at  DATETIME
    UNIQUE (horse_id, date, course)
```

### 3-3. 特徴量への統合（将来拡張）

- 最終追い切りタイム（レース直前の調教評価）を `horse_features.py` に追加可能
- 本サイクルでは DB 格納まで実装、特徴量化は第3サイクル以降

---

## 実装優先度まとめ

| 実装項目 | 優先度 | 新規ファイル |
|---------|--------|------------|
| SHAP 統合 (`model/explainer.py`) | 高 | ✅ |
| 予測ページ SHAP グラフ | 高 | 既存拡張 |
| フォールバックパーサー (`scraper/base.py`) | 高 | 既存拡張 |
| データバリデーター (`db/validator.py`) | 高 | ✅ |
| `scripts/validate_data.py` | 中 | ✅ |
| 上がり3F偏差特徴量 | 高 | 既存拡張 |
| Optuna チューナー (`model/tuner.py`) | 中 | ✅ |
| `scripts/tune_model.py` | 中 | ✅ |
| ペース係数改良 | 中 | 既存拡張 |
| 斤量×距離交差項 | 低 | 既存拡張 |
| 調教タイムスクレイパー | 中 | ✅ |
