# データモデル設計 — 競馬予想AI

## 1. ER 図

```
┌──────────────┐       ┌──────────────────────────────────────────────┐
│   stallions  │       │                  race_entries                  │
│──────────────│       │──────────────────────────────────────────────│
│ horse_id (PK)│◄──┐   │ race_id (FK→races)                           │
│ name         │   │   │ horse_id (FK→horses)                         │
└──────────────┘   │   │ jockey_id (FK→jockeys)                       │
                   │   │ trainer_id (FK→trainers)                     │
┌──────────────┐   │   │ post_position                                 │
│    horses    │   │   │ finish_position (NULL=出走予定)               │
│──────────────│   │   │ time                                          │
│ horse_id (PK)│───┘   │ last_3f_time                                  │
│ name         │       │ win_odds                                      │
│ sex          │       │ place_odds                                    │
│ birth_date   │       │ quinella_odds (JSON)                          │
│ trainer_id   │       │ trifecta_odds (JSON)                          │
│ sire_id      │       │ horse_weight                                  │
│ dam_id       │       │ weight_diff                                   │
│ brood_sire_id│       │ handicap_weight                               │
└──────────────┘       │ running_style                                 │
                       │ corner_positions (JSON)                       │
┌──────────────┐       └──────────────────────────────────────────────┘
│   jockeys    │                    │                  │
│──────────────│                    ▼                  ▼
│ jockey_id(PK)│       ┌────────────────┐   ┌─────────────────────┐
│ name         │       │     races      │   │    odds_history      │
└──────────────┘       │────────────────│   │─────────────────────│
                       │ race_id (PK)   │   │ id (PK autoincrement)│
┌──────────────┐       │ date           │   │ race_id (FK→races)  │
│   trainers   │       │ venue          │   │ horse_id (FK→horses)│
│──────────────│       │ course_id      │   │ timestamp           │
│trainer_id(PK)│       │ distance       │   │ win_odds            │
│ name         │       │ surface        │   └─────────────────────┘
│ stable       │       │ weather        │
└──────────────┘       │ going          │   ┌─────────────────────┐
                       │ grade          │   │       courses        │
                       │ field_size     │   │─────────────────────│
                       │ lap_times(JSON)│   │ course_id (PK)      │
                       │ straight_length│   │ venue               │
                       │ num_curves     │   │ surface             │
                       └────────────────┘   │ distance            │
                                            │ straight_length     │
                                            │ num_curves          │
                                            │ has_slope           │
                                            │ course_note         │
                                            └─────────────────────┘
```

---

## 2. テーブル定義（DDL）

### `races` テーブル
```sql
CREATE TABLE races (
    race_id         TEXT PRIMARY KEY,   -- 例: 202301010101
    date            DATE NOT NULL,       -- 開催日
    venue           TEXT NOT NULL,       -- 競馬場名（東京・中山等）
    course_id       TEXT,               -- courses テーブル参照用
    distance        INTEGER NOT NULL,    -- 距離（メートル）
    surface         TEXT NOT NULL,       -- 芝/ダート/障害
    weather         TEXT,               -- 晴/曇/雨/小雨/雪
    going           TEXT,               -- 良/稍重/重/不良
    grade           TEXT,               -- G1/G2/G3/OP/L/3勝/2勝/1勝/未勝利/新馬
    field_size      INTEGER,            -- 出走頭数
    lap_times       TEXT,               -- JSON配列: [12.3, 11.5, ...]
    straight_length REAL,               -- 直線距離（m）
    num_curves      INTEGER,            -- コーナー数
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `race_entries` テーブル
```sql
CREATE TABLE race_entries (
    race_id             TEXT NOT NULL REFERENCES races(race_id),
    horse_id            TEXT NOT NULL REFERENCES horses(horse_id),
    jockey_id           TEXT REFERENCES jockeys(jockey_id),
    trainer_id          TEXT REFERENCES trainers(trainer_id),
    post_position       INTEGER,        -- 枠番
    finish_position     INTEGER,        -- 着順（NULL=出走予定）
    time                REAL,           -- タイム（秒）
    last_3f_time        REAL,           -- 上がり3Fタイム（秒）
    win_odds            REAL,           -- 単勝オッズ
    place_odds          REAL,           -- 複勝オッズ（上限）
    quinella_odds       TEXT,           -- 馬連オッズ JSON
    trifecta_odds       TEXT,           -- 3連複オッズ JSON
    horse_weight        INTEGER,        -- 馬体重（kg）
    weight_diff         INTEGER,        -- 馬体重増減（前走比）
    handicap_weight     REAL,           -- 斤量（kg）
    running_style       TEXT,           -- 脚質（逃/先/差/追/マ）
    corner_positions    TEXT,           -- コーナー通過順位 JSON [1,2,3,4]
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, horse_id)
);
```

### `horses` テーブル
```sql
CREATE TABLE horses (
    horse_id            TEXT PRIMARY KEY,  -- netkeiba 馬ID
    name                TEXT NOT NULL,
    sex                 TEXT,              -- 牡/牝/セン
    birth_date          DATE,
    trainer_id          TEXT REFERENCES trainers(trainer_id),
    sire_id             TEXT REFERENCES stallions(horse_id),   -- 父
    dam_id              TEXT REFERENCES stallions(horse_id),   -- 母
    broodmare_sire_id   TEXT REFERENCES stallions(horse_id),   -- 母父
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `jockeys` テーブル
```sql
CREATE TABLE jockeys (
    jockey_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `trainers` テーブル
```sql
CREATE TABLE trainers (
    trainer_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    stable      TEXT,               -- 所属厩舎（栗東/美浦）
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `stallions` テーブル（血統マスタ）
```sql
CREATE TABLE stallions (
    horse_id    TEXT PRIMARY KEY,   -- 父・母・母父の馬ID
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `odds_history` テーブル
```sql
CREATE TABLE odds_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id     TEXT NOT NULL REFERENCES races(race_id),
    horse_id    TEXT NOT NULL REFERENCES horses(horse_id),
    timestamp   TIMESTAMP NOT NULL,
    win_odds    REAL NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_odds_history_race_horse ON odds_history(race_id, horse_id);
```

### `courses` テーブル
```sql
CREATE TABLE courses (
    course_id       TEXT PRIMARY KEY,  -- 例: tokyo_turf_2000
    venue           TEXT NOT NULL,
    surface         TEXT NOT NULL,
    distance        INTEGER NOT NULL,
    straight_length REAL,
    num_curves      INTEGER,
    has_slope       BOOLEAN DEFAULT FALSE,
    course_note     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. インデックス

```sql
-- よく使うクエリ用インデックス
CREATE INDEX idx_race_entries_horse ON race_entries(horse_id, race_id);
CREATE INDEX idx_race_entries_jockey ON race_entries(jockey_id, race_id);
CREATE INDEX idx_race_entries_trainer ON race_entries(trainer_id, race_id);
CREATE INDEX idx_races_date ON races(date);
CREATE INDEX idx_races_venue ON races(venue, date);
```

---

## 4. 命名規則

| 項目 | 規則 | 例 |
|------|------|----|
| race_id | YYYYMMDDnnrr (年月日・開催回・レース番号) | 202401010101 |
| horse_id | netkeiba の馬IDをそのまま使用 | 2019105765 |
| jockey_id | netkeiba の騎手IDをそのまま使用 | 01088 |
| trainer_id | netkeiba の調教師IDをそのまま使用 | 01013 |
| surface | 芝 / ダート / 障害 | 芝 |
| going | 良 / 稍重 / 重 / 不良 | 良 |
| grade | G1 / G2 / G3 / OP / L / 3勝 / 2勝 / 1勝 / 未勝利 / 新馬 | G1 |
| running_style | 逃 / 先 / 差 / 追 / マ（マクリ） | 先 |

---

## 5. upsert 方針

SQLAlchemy の `insert(...).on_conflict_do_update()` を使用して冪等な書き込みを実現する。  
`race_id` + `horse_id` の複合主キーで重複判定を行い、既存レコードは全カラムを上書き更新する。
