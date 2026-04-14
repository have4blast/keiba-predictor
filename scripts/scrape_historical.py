"""過去レースデータ一括収集スクリプト

使用例:
    python scripts/scrape_historical.py --start 2023-01-01 --end 2023-12-31
    python scripts/scrape_historical.py --start 2023-01-01 --end 2023-12-31 --resume
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date, timedelta
import click
from loguru import logger
from tqdm import tqdm

from db import init_db, get_session
from db.crud import (
    upsert_race, upsert_race_entry, upsert_horse, upsert_jockey,
    upsert_trainer, upsert_stallion, upsert_odds_history,
    get_scraped_race_ids, horse_exists, jockey_exists, trainer_exists,
)
from scraper.base import RateLimitedSession
from scraper.race_list import fetch_race_ids
from scraper.race_detail import fetch_race_detail
from scraper.horse_profile import fetch_horse_profile
from scraper.jockey_profile import fetch_jockey_profile
from scraper.trainer_profile import fetch_trainer_profile
from scraper.odds import fetch_odds


def _daterange(start: date, end: date):
    """start〜end の日付を1日ずつ生成"""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


@click.command()
@click.option("--start", required=True, type=click.DateTime(formats=["%Y-%m-%d"]),
              help="収集開始日 (YYYY-MM-DD)")
@click.option("--end",   required=True, type=click.DateTime(formats=["%Y-%m-%d"]),
              help="収集終了日 (YYYY-MM-DD)")
@click.option("--resume", is_flag=True, default=False,
              help="スクレイピング済み race_id をスキップして再開")
def main(start, end, resume: bool) -> None:
    """過去レースデータの一括収集"""
    logger.add("logs/scrape_historical.log", rotation="10 MB")
    logger.info(f"開始: {start.date()} 〜 {end.date()}, resume={resume}")

    init_db()
    session = get_session()
    http = RateLimitedSession()

    # resume モードで既存レースIDを取得
    scraped_ids: set[str] = get_scraped_race_ids(session) if resume else set()
    logger.info(f"既存レースID数: {len(scraped_ids)}")

    all_dates = list(_daterange(start.date(), end.date()))

    for current_date in tqdm(all_dates, desc="日付"):
        date_str = current_date.strftime("%Y%m%d")
        race_ids = fetch_race_ids(http, date_str)

        for race_id in tqdm(race_ids, desc=f"{date_str}", leave=False):
            if resume and race_id in scraped_ids:
                continue

            # ── レース詳細取得 ────────────────────────────────
            detail = fetch_race_detail(http, race_id)
            if not detail:
                continue

            try:
                upsert_race(session, detail["race"])

                # オッズ取得
                odds_data = fetch_odds(http, race_id)

                for entry in detail["entries"]:
                    if not entry.get("horse_id"):
                        continue

                    # オッズ付与
                    if odds_data:
                        horse_num = str(entry.get("post_position", ""))
                        entry["win_odds"] = odds_data["win"].get(horse_num, entry.get("win_odds"))

                    upsert_race_entry(session, entry)

                    # ── 馬プロフィール（未取得のみ） ────────────
                    horse_id = entry["horse_id"]
                    if not horse_exists(session, horse_id):
                        prof = fetch_horse_profile(http, horse_id)
                        if prof:
                            upsert_horse(session, prof["horse"])
                            for s in prof["stallions"]:
                                upsert_stallion(session, s)

                    # ── 騎手プロフィール（未取得のみ） ──────────
                    jockey_id = entry.get("jockey_id")
                    if jockey_id and not jockey_exists(session, jockey_id):
                        prof = fetch_jockey_profile(http, jockey_id)
                        if prof:
                            upsert_jockey(session, prof)

                    # ── 調教師プロフィール（未取得のみ） ────────
                    trainer_id = entry.get("trainer_id")
                    if trainer_id and not trainer_exists(session, trainer_id):
                        prof = fetch_trainer_profile(http, trainer_id)
                        if prof:
                            upsert_trainer(session, prof)

                # オッズ変動履歴の保存
                if odds_data:
                    from datetime import datetime
                    ts = odds_data["timestamp"]
                    for horse_num, win_odds in odds_data["win"].items():
                        # horse_num → horse_id は race_entries から引く
                        # （簡略化: horse_num=post_position として近似）
                        pass  # odds_history は別途実装可能

                session.commit()
                logger.debug(f"Saved race {race_id} ({len(detail['entries'])} entries)")

            except Exception as e:
                session.rollback()
                logger.error(f"Error saving race {race_id}: {e}")

    session.close()
    logger.info("収集完了")


if __name__ == "__main__":
    main()
