"""開催日ごとのレースID一覧を取得"""
import re
from loguru import logger
from bs4 import BeautifulSoup
from scraper.base import RateLimitedSession


def fetch_race_ids(session: RateLimitedSession, date_str: str) -> list[str]:
    """
    date_str: 'YYYYMMDD' 形式の開催日
    returns: race_id のリスト（例: ['202401010101', ...]）
    """
    url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
    try:
        resp = session.get(url, encoding="utf-8")
    except Exception as e:
        logger.warning(f"race_list fetch failed for {date_str}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    race_ids: list[str] = []

    # レースリンクから race_id を抽出
    # 例: href="/race/result.html?race_id=202401010101"
    for a in soup.find_all("a", href=re.compile(r"race_id=\d{12}")):
        m = re.search(r"race_id=(\d{12})", a["href"])
        if m:
            race_ids.append(m.group(1))

    # 重複除去・ソート
    race_ids = sorted(set(race_ids))
    logger.info(f"{date_str}: {len(race_ids)} races found")
    return race_ids
