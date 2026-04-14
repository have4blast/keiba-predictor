"""騎手プロフィール取得"""
from typing import Any
from loguru import logger
from bs4 import BeautifulSoup
from scraper.base import RateLimitedSession


def fetch_jockey_profile(
    session: RateLimitedSession, jockey_id: str
) -> dict[str, Any] | None:
    url = f"https://db.netkeiba.com/jockey/{jockey_id}/"
    try:
        resp = session.get(url, encoding="euc-jp")
    except Exception as e:
        logger.warning(f"jockey_profile fetch failed for {jockey_id}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    name_tag = soup.find("h1", class_="horse_title") or soup.find("div", class_="jockey_title")
    if name_tag:
        name = name_tag.get_text(strip=True)
    else:
        title = soup.find("title")
        name = title.get_text(strip=True).split("|")[0].strip() if title else jockey_id

    return {"jockey_id": jockey_id, "name": name}
