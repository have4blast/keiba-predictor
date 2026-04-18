"""サンプルデータ生成スクリプト

ネットワーク不要で現実的なダミーレースデータを SQLite に投入する。
パイプライン全体（build_features → train_model → dashboard）の動作確認用。

使用例:
    python scripts/generate_sample_data.py
    python scripts/generate_sample_data.py --races 500 --db data/keiba.db
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import random
import math
from datetime import date, timedelta, datetime
from pathlib import Path

import click
import numpy as np
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.models import Base, Race, RaceEntry, Horse, Jockey, Trainer, Stallion, OddsHistory, Course

# ─────────────────────────────────────────────
# マスタデータ定義
# ─────────────────────────────────────────────

VENUES = ["東京", "中山", "阪神", "京都", "中京", "小倉", "福島", "新潟", "札幌", "函館"]

VENUE_SURFACES = {
    "東京": {"芝": [1400, 1600, 1800, 2000, 2400, 3400], "ダート": [1300, 1400, 1600, 2100]},
    "中山": {"芝": [1200, 1600, 1800, 2000, 2200, 3600], "ダート": [1200, 1800]},
    "阪神": {"芝": [1200, 1400, 1600, 1800, 2000, 2200], "ダート": [1200, 1400, 1800, 2000]},
    "京都": {"芝": [1200, 1400, 1600, 1800, 2000, 2200, 3000], "ダート": [1200, 1400, 1800, 1900]},
    "中京": {"芝": [1200, 1400, 2000], "ダート": [1200, 1400, 1800]},
    "小倉": {"芝": [1200, 1800, 2000], "ダート": [1000, 1700]},
    "福島": {"芝": [1200, 1800, 2000], "ダート": [1150, 1700]},
    "新潟": {"芝": [1000, 1200, 1400, 1600, 2000], "ダート": [1200, 1800]},
    "札幌": {"芝": [1200, 1500, 1800, 2000], "ダート": [1000, 1700]},
    "函館": {"芝": [1200, 1800, 2000], "ダート": [1000, 1700]},
}

VENUE_STRAIGHT = {
    "東京": 525.9, "中山": 310.0, "阪神": 473.6, "京都": 328.4,
    "中京": 412.5, "小倉": 291.3, "福島": 292.0, "新潟": 658.7,
    "札幌": 264.3, "函館": 262.1,
}

GRADES   = ["新馬", "未勝利", "1勝", "2勝", "3勝", "OP", "G3", "G2", "G1"]
GRADE_W  = [0.12, 0.30, 0.25, 0.15, 0.08, 0.05, 0.03, 0.01, 0.01]
WEATHERS = ["晴", "曇", "雨", "小雨"]
GOINGS   = ["良", "稍重", "重", "不良"]
GOING_W  = [0.55, 0.25, 0.13, 0.07]
SEXES    = ["牡", "牝", "セン"]
SEX_W    = [0.50, 0.35, 0.15]
STYLES   = ["逃", "先", "差", "追"]
STABLES  = ["栗東", "美浦"]

JOCKEY_NAMES = [
    "川田将雅", "福永祐一", "武豊", "戸崎圭太", "横山武史",
    "松山弘平", "池添謙一", "岩田康誠", "和田竜二", "浜中俊",
    "石橋脩", "幸英明", "丸田恭介", "藤岡佑介", "北村友一",
    "三浦皇成", "吉田隼人", "田辺裕信", "坂井瑠星", "津村明秀",
    "レーン", "デムーロ", "ムーア", "ルメール", "ボウマン",
    "モレイラ", "スミヨン", "マクドナルド", "ビュイック", "ホワイト",
]

TRAINER_NAMES = [
    ("矢作芳人", "栗東"), ("国枝栄", "美浦"), ("堀宣行", "美浦"), ("池江泰寿", "栗東"),
    ("藤原英昭", "栗東"), ("音無秀孝", "栗東"), ("高野友和", "栗東"), ("須貝尚介", "栗東"),
    ("友道康夫", "栗東"), ("中内田充正", "栗東"), ("木村哲也", "美浦"), ("戸田博文", "栗東"),
    ("角居勝彦", "栗東"), ("斉藤崇史", "美浦"), ("鹿戸雄一", "美浦"), ("大竹正博", "美浦"),
    ("松田博資", "栗東"), ("橋田満", "栗東"), ("清水英克", "栗東"), ("伊藤圭三", "栗東"),
]

STALLION_NAMES = [
    "ディープインパクト", "キングカメハメハ", "ハーツクライ", "ステイゴールド",
    "ロードカナロア", "モーリス", "エピファネイア", "ドゥラメンテ",
    "ハービンジャー", "オルフェーヴル", "ゴールドシップ", "キズナ",
    "ダイワメジャー", "スクリーンヒーロー", "アドマイヤムーン", "マンハッタンカフェ",
    "フランケル", "ガリレオ", "シーザスターズ", "デインヒル",
]

HORSE_PREFIXES = [
    "サンライズ", "シャイニング", "ゴールデン", "ブルーム", "ホワイト",
    "ブラック", "レッド", "シルバー", "ダーク", "ライト",
    "ランニング", "ドリーム", "スペシャル", "マジック", "パワー",
    "スピード", "フラッシュ", "スター", "サニー", "ブリリアント",
]

HORSE_SUFFIXES = [
    "ホース", "ランナー", "ウィナー", "ライダー", "キング",
    "クイーン", "プリンス", "プリンセス", "ロード", "スター",
    "アロー", "ダッシュ", "ブレイブ", "ノーブル", "グレイト",
    "サンダー", "ライトニング", "ストーム", "グローリー", "リーダー",
]

# ─────────────────────────────────────────────
# ユーティリティ関数
# ─────────────────────────────────────────────

def _race_time_sec(distance: int, surface: str, going: str) -> float:
    """距離・馬場から基準タイム（秒）を推定する"""
    base = distance / 1000 * 59.5 if surface == "芝" else distance / 1000 * 61.5
    going_adj = {"良": 0.0, "稍重": 0.8, "重": 1.8, "不良": 3.5}.get(going, 0.0)
    noise = random.gauss(0, 0.5)
    return round(base + going_adj + noise, 1)


def _generate_odds(field_size: int, winner_pos: int) -> list[float]:
    """各馬のオッズを生成する（winner_pos が 1 着）"""
    raw = [random.uniform(1.0, 5.0) for _ in range(field_size)]
    # winner の強さを少し盛る（必ずしも 1 番人気ではない）
    raw[winner_pos] *= 0.5
    # 正規化して実際のオッズ風に
    total = sum(1 / r for r in raw)
    odds = [round(0.75 / (1 / r / total) + random.gauss(0, 0.3), 1) for r in raw]
    return [max(1.1, o) for o in odds]


def _corner_positions(post: int, style: str, field: int) -> list[int]:
    """コーナー通過順位を脚質から擬似生成する"""
    if style == "逃":
        base = 1
    elif style == "先":
        base = random.randint(2, max(2, field // 4))
    elif style == "差":
        base = random.randint(field // 4, field // 2)
    else:
        base = random.randint(field // 2, field - 1)
    positions = []
    for _ in range(4):
        jitter = random.randint(-1, 1)
        positions.append(max(1, min(field, base + jitter)))
    return positions


def _lap_times(distance: int, total_time: float) -> list[float]:
    """ラップタイムリストを生成する"""
    n_laps = distance // 200
    if n_laps == 0:
        return []
    base_lap = total_time / n_laps
    laps = []
    for i in range(n_laps):
        if i == 0:
            lap = base_lap * random.uniform(1.05, 1.15)
        elif i == n_laps - 1:
            lap = base_lap * random.uniform(0.88, 0.96)
        else:
            lap = base_lap * random.uniform(0.97, 1.03)
        laps.append(round(lap, 1))
    return laps


# ─────────────────────────────────────────────
# メイン生成ロジック
# ─────────────────────────────────────────────

@click.command()
@click.option("--races", default=600, type=int, help="生成レース数（目安）")
@click.option("--db",    default="data/keiba.db", help="SQLite DB パス")
@click.option("--start", default="2022-01-01", help="開始日 (YYYY-MM-DD)")
@click.option("--end",   default="2023-03-31", help="終了日 (YYYY-MM-DD)")
@click.option("--seed",  default=42,  type=int,  help="乱数シード")
def main(races: int, db: str, start: str, end: str, seed: int) -> None:
    """現実的なダミーレースデータを生成して SQLite に投入する"""
    random.seed(seed)
    np.random.seed(seed)

    Path(db).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)

    logger.info(f"DB: {db}")
    logger.info(f"期間: {start} 〜 {end}, 目標レース数: {races}")

    with Session(engine) as session:
        # ── 1. マスタデータ投入 ──────────────────────────
        logger.info("種牡馬マスタを生成中...")
        stallions = []
        for i, name in enumerate(STALLION_NAMES):
            sid = f"S{i+1:04d}"
            if not session.get(Stallion, sid):
                session.add(Stallion(horse_id=sid, name=name))
            stallions.append(sid)
        session.flush()

        logger.info("調教師マスタを生成中...")
        trainer_ids = []
        for i, (name, stable) in enumerate(TRAINER_NAMES):
            tid = f"T{i+1:04d}"
            if not session.get(Trainer, tid):
                session.add(Trainer(trainer_id=tid, name=name, stable=stable))
            trainer_ids.append(tid)
        session.flush()

        logger.info("騎手マスタを生成中...")
        jockey_ids = []
        for i, name in enumerate(JOCKEY_NAMES):
            jid = f"J{i+1:04d}"
            if not session.get(Jockey, jid):
                session.add(Jockey(jockey_id=jid, name=name))
            jockey_ids.append(jid)
        session.flush()

        logger.info("馬マスタを生成中...")
        n_horses = max(300, races * 2)
        horse_ids = []
        base_year = int(start[:4]) - 5
        for i in range(n_horses):
            hid = f"H{i+1:05d}"
            if not session.get(Horse, hid):
                name = random.choice(HORSE_PREFIXES) + random.choice(HORSE_SUFFIXES)
                birth_year  = random.randint(base_year, base_year + 3)
                birth_month = random.randint(1, 6)
                session.add(Horse(
                    horse_id=hid,
                    name=f"{name}{i+1}",
                    sex=random.choices(SEXES, weights=SEX_W)[0],
                    birth_date=date(birth_year, birth_month, 1),
                    trainer_id=random.choice(trainer_ids),
                    sire_id=random.choice(stallions),
                    dam_id=random.choice(stallions),
                    broodmare_sire_id=random.choice(stallions),
                ))
            horse_ids.append(hid)
        session.flush()

        logger.info("コースマスタを生成中...")
        for venue, surf_dist in VENUE_SURFACES.items():
            for surface, distances in surf_dist.items():
                for dist in distances:
                    cid = f"{venue}_{surface}_{dist}"
                    if not session.get(Course, cid):
                        session.add(Course(
                            course_id=cid,
                            venue=venue,
                            surface=surface,
                            distance=dist,
                            straight_length=VENUE_STRAIGHT.get(venue),
                            num_curves=4 if dist >= 1600 else 2,
                            has_slope=(venue == "中山" and surface == "芝"),
                        ))
        session.flush()

        # ── 2. レース・出走データ生成 ─────────────────────
        logger.info("レースデータを生成中...")

        start_dt = date.fromisoformat(start)
        end_dt   = date.fromisoformat(end)

        # 開催日（土日のみ）を列挙
        race_days: list[date] = []
        d = start_dt
        while d <= end_dt:
            if d.weekday() in (5, 6):  # 土・日
                race_days.append(d)
            d += timedelta(days=1)

        race_count = 0
        horse_style_cache: dict[str, str] = {}

        for race_date in race_days:
            if race_count >= races:
                break

            # その日の開催場（2〜3場）
            n_venues = random.randint(2, 3)
            day_venues = random.sample(VENUES, n_venues)
            weather_today = random.choices(WEATHERS, weights=[0.5, 0.3, 0.15, 0.05])[0]
            going_today   = random.choices(GOINGS, weights=GOING_W)[0]

            for venue in day_venues:
                if race_count >= races:
                    break

                n_races = random.randint(8, 11)
                avail_surfs = list(VENUE_SURFACES[venue].keys())

                for race_num in range(1, n_races + 1):
                    if race_count >= races:
                        break

                    surface  = random.choice(avail_surfs)
                    dist_opt = VENUE_SURFACES[venue][surface]
                    distance = random.choice(dist_opt)
                    grade    = random.choices(GRADES, weights=GRADE_W)[0]
                    field_sz = random.randint(8, 18)
                    course_id = f"{venue}_{surface}_{distance}"

                    race_id = (
                        f"{race_date.strftime('%Y%m%d')}"
                        f"{VENUES.index(venue)+1:02d}"
                        f"{race_num:02d}"
                    )

                    if session.get(Race, race_id):
                        continue

                    race = Race(
                        race_id=race_id,
                        date=race_date,
                        venue=venue,
                        course_id=course_id,
                        distance=distance,
                        surface=surface,
                        weather=weather_today,
                        going=going_today,
                        grade=grade,
                        field_size=field_sz,
                        straight_length=VENUE_STRAIGHT.get(venue),
                        num_curves=4 if distance >= 1600 else 2,
                    )

                    # 出走馬を抽選
                    entry_horses = random.sample(horse_ids, field_sz)
                    entry_jockeys = random.sample(jockey_ids, min(field_sz, len(jockey_ids)))
                    while len(entry_jockeys) < field_sz:
                        entry_jockeys.append(random.choice(jockey_ids))

                    # 各馬の能力スコア（オッズ生成に使用）
                    abilities = [random.gauss(0, 1) for _ in range(field_sz)]
                    # 上位馬を 1 着として選択（能力高い馬が勝ちやすい）
                    probs = [math.exp(a) for a in abilities]
                    total_p = sum(probs)
                    probs_norm = [p / total_p for p in probs]
                    winner_idx = int(np.random.choice(range(field_sz), p=probs_norm))

                    # オッズ生成（能力の逆数ベース）
                    raw_odds = [max(1.1, round(total_p / p * 0.75 + random.gauss(0, 0.3), 1))
                                for p in probs]

                    # 着順を能力ベースで決定
                    ability_with_noise = [a + random.gauss(0, 0.5) for a in abilities]
                    finish_order = sorted(range(field_sz), key=lambda i: -ability_with_noise[i])

                    win_time = _race_time_sec(distance, surface, going_today)
                    laps = _lap_times(distance, win_time)
                    race.lap_times = json.dumps(laps)
                    session.add(race)

                    for pos_idx, horse_pos in enumerate(range(field_sz)):
                        hid = entry_horses[horse_pos]
                        jid = entry_jockeys[horse_pos]

                        # 馬の脚質（初回は乱数、以降は一貫性を持たせる）
                        if hid not in horse_style_cache:
                            horse_style_cache[hid] = random.choices(
                                STYLES, weights=[0.10, 0.30, 0.35, 0.25]
                            )[0]
                        style = horse_style_cache[hid]

                        finish_pos = finish_order.index(horse_pos) + 1
                        place_bonus = 1 if finish_pos <= 3 else 0

                        # タイム（1着基準 + 着差）
                        gap = max(0.0, (finish_pos - 1) * random.uniform(0.2, 0.6))
                        entry_time = round(win_time + gap, 1) if finish_pos > 1 else win_time
                        last3f = round(random.gauss(34.5, 1.0), 1)
                        last3f = max(32.0, min(38.0, last3f))

                        corners = _corner_positions(horse_pos + 1, style, field_sz)
                        base_weight = random.randint(440, 530)
                        weight_diff = random.randint(-10, 10)

                        trainer_id = session.get(Horse, hid).trainer_id

                        entry = RaceEntry(
                            race_id=race_id,
                            horse_id=hid,
                            jockey_id=jid,
                            trainer_id=trainer_id,
                            post_position=horse_pos + 1,
                            finish_position=finish_pos,
                            time=entry_time,
                            last_3f_time=last3f,
                            win_odds=raw_odds[horse_pos],
                            place_odds=round(raw_odds[horse_pos] / 3, 1),
                            horse_weight=base_weight,
                            weight_diff=weight_diff,
                            handicap_weight=round(random.uniform(50.0, 58.0), 1),
                            running_style=style,
                            corner_positions=json.dumps(corners),
                        )
                        session.add(entry)

                        # オッズ変動履歴（レース前 2 スナップショット）
                        for hours_before in [3, 1]:
                            ts = datetime.combine(
                                race_date,
                                datetime.min.time()
                            ).replace(hour=10 + race_num) - timedelta(hours=hours_before)
                            fluctuation = random.uniform(0.85, 1.15)
                            session.add(OddsHistory(
                                race_id=race_id,
                                horse_id=hid,
                                timestamp=ts,
                                win_odds=round(raw_odds[horse_pos] * fluctuation, 1),
                            ))

                    race_count += 1

            if race_count % 100 == 0 and race_count > 0:
                session.flush()
                logger.info(f"  {race_count} レース生成済み...")

        session.commit()

    # ── 3. 集計レポート ───────────────────────────
    from sqlalchemy import text
    with engine.connect() as conn:
        def count(table):
            return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

        print("\n=== 生成完了 ===")
        print(f"  レース数       : {count('races'):,}")
        print(f"  出走エントリ   : {count('race_entries'):,}")
        print(f"  馬             : {count('horses'):,}")
        print(f"  騎手           : {count('jockeys'):,}")
        print(f"  調教師         : {count('trainers'):,}")
        print(f"  種牡馬         : {count('stallions'):,}")
        print(f"  オッズ履歴     : {count('odds_history'):,}")
        print(f"  コース         : {count('courses'):,}")
        print(f"\n保存先: {db}")
        print("\n次のステップ:")
        print("  python scripts/build_features.py")
        print("  python scripts/train_model.py")
        print("  streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
