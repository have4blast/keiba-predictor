"""翌日出走表収集スクリプト

使用例:
    python scripts/scrape_upcoming.py
    python scripts/scrape_upcoming.py --date 2024-01-15
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
    upsert_trainer, horse_exists, jockey_exists, trainer_exists,
)
from scraper.base import RateLimitedSession
from scraper.race_list import fetch_race_ids
from scraper.upcoming import fetch_upcoming_race
from scraper.horse_profile import fetch_horse_profile
from scraper.jockey_profile import fetch_jockey_profile
from scraper.trainer_profile import fetch_trainer_profile


@click.command()
@click.option("--date", "target_date",
              type=click.DateTime(formats=["%Y-%m-%d"]),
              default=None,
              help="収集対象日（省略時: 翌日）")
def main(target_date) -> None:
    """翌日出走表の収集（finish_position=NULL で格納）"""
    logger.add("logs/scrape_upcoming.log", rotation="10 MB")

    if target_date is None:
        target = date.today() + timedelta(days=1)
    else:
        target = target_date.date()

    date_str = target.strftime("%Y%m%d")
    logger.info(f"出走表収集対象日: {target}")

    init_db()
    session = get_session()
    http = RateLimitedSession()

    race_ids = fetch_race_ids(http, date_str)
    if not race_ids:
        logger.info("対象レースなし")
        return

    logger.info(f"{len(race_ids)} レース取得開始")

    for race_id in tqdm(race_ids, desc="出走表"):
        detail = fetch_upcoming_race(http, race_id)
        if not detail:
            continue

        try:
            upsert_race(session, detail["race"])

            for entry in detail["entries"]:
                if not entry.get("horse_id"):
                    continue

                upsert_race_entry(session, entry)

                # 馬プロフィール（未取得のみ）
                horse_id = entry["horse_id"]
                if not horse_exists(session, horse_id):
                    prof = fetch_horse_profile(http, horse_id)
                    if prof:
                        upsert_horse(session, prof["horse"])

                # 騎手プロフィール（未取得のみ）
                jockey_id = entry.get("jockey_id")
                if jockey_id and not jockey_exists(session, jockey_id):
                    prof = fetch_jockey_profile(http, jockey_id)
                    if prof:
                        upsert_jockey(session, prof)

                # 調教師プロフィール（未取得のみ）
                trainer_id = entry.get("trainer_id")
                if trainer_id and not trainer_exists(session, trainer_id):
                    prof = fetch_trainer_profile(http, trainer_id)
                    if prof:
                        upsert_trainer(session, prof)

            session.commit()
            logger.debug(f"Saved upcoming race {race_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error saving upcoming race {race_id}: {e}")

    session.close()
    logger.info(f"出走表収集完了: {len(race_ids)} レース")


if __name__ == "__main__":
    main()
