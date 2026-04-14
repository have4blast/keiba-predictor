"""調教師プロフィール取得"""
import re
from typing import Any
from loguru import logger
from bs4 import BeautifulSoup
from scraper.base import RateLimitedSession


def fetch_trainer_profile(
    session: RateLimitedSession, trainer_id: str
) -> dict[str, Any] | None:
    url = f"https://db.netkeiba.com/trainer/{trainer_id}/"
    try:
        resp = session.get(url, encoding="euc-jp")
    except Exception as e:
        logger.warning(f"trainer_profile fetch failed for {trainer_id}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    name_tag = soup.find("h1") or soup.find("div", class_="trainer_title")
    name = name_tag.get_text(strip=True) if name_tag else trainer_id

    # 所属厩舎（栗東/美浦）
    stable = None
    text = soup.get_text()
    if "栗東" in text:
        stable = "栗東"
    elif "美浦" in text:
        stable = "美浦"

    return {"trainer_id": trainer_id, "name": name, "stable": stable}
