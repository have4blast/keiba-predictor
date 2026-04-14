"""翌日出走表（shutuba）取得"""
import re
from typing import Any
from loguru import logger
from bs4 import BeautifulSoup
from scraper.base import RateLimitedSession


def fetch_upcoming_race(
    session: RateLimitedSession, race_id: str
) -> dict[str, Any] | None:
    """
    出走予定レースの情報を取得する。
    finish_position=NULL で race_entries に格納するためのデータを返す。

    returns: {
        "race":    {...},   # races テーブル用
        "entries": [...],   # race_entries テーブル用（finish_position=None）
    }
    """
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    try:
        resp = session.get(url, encoding="utf-8")
    except Exception as e:
        logger.warning(f"upcoming fetch failed for {race_id}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # ── レース基本情報 ─────────────────────────────────────────
    year  = race_id[:4]
    month = race_id[4:6]
    day   = race_id[6:8]
    from datetime import date
    race_info: dict[str, Any] = {
        "race_id": race_id,
        "date": date(int(year), int(month), int(day)),
    }

    venue_map = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }
    race_info["venue"] = venue_map.get(race_id[8:10], race_id[8:10])

    # レース条件テキスト
    race_cond = soup.find("div", class_="RaceData01")
    if race_cond:
        text = race_cond.get_text()
        m = re.search(r"(芝|ダート|障害)\s*(\d+)m", text)
        if m:
            race_info["surface"]  = m.group(1)
            race_info["distance"] = int(m.group(2))
        m = re.search(r"天候\s*:\s*(\S+)", text)
        if m:
            race_info["weather"] = m.group(1)
        m = re.search(r"馬場\s*:\s*(\S+)", text)
        if m:
            race_info["going"] = m.group(1)

    # ── 出走表テーブル ─────────────────────────────────────────
    shutuba_table = (
        soup.find("table", class_="Shutuba_Table")
        or soup.find("table", class_=re.compile(r"shutuba", re.I))
    )
    entries: list[dict[str, Any]] = []

    if not shutuba_table:
        logger.warning(f"Shutuba table not found for race {race_id}")
        return {"race": race_info, "entries": []}

    rows = shutuba_table.find_all("tr", class_=re.compile(r"HorseList|HorseInfo"))
    if not rows:
        rows = shutuba_table.find_all("tr")[1:]

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        entry: dict[str, Any] = {
            "race_id":         race_id,
            "finish_position": None,  # 出走予定
        }

        # 枠番
        try:
            entry["post_position"] = int(cols[0].get_text(strip=True))
        except ValueError:
            pass

        # 馬名リンク → horse_id
        horse_link = row.find("a", href=re.compile(r"/horse/(\d+)"))
        if horse_link:
            m = re.search(r"/horse/(\d+)", horse_link["href"])
            entry["horse_id"] = m.group(1) if m else None
        if not entry.get("horse_id"):
            continue

        # 斤量
        for col in cols:
            text = col.get_text(strip=True)
            if re.match(r"^\d{2}\.\d$", text):
                try:
                    entry["handicap_weight"] = float(text)
                except ValueError:
                    pass
                break

        # 騎手リンク → jockey_id
        jockey_link = row.find("a", href=re.compile(r"/jockey/\w+/"))
        if jockey_link:
            m = re.search(r"/jockey/(\w+)/", jockey_link["href"])
            entry["jockey_id"] = m.group(1) if m else None

        # 調教師リンク → trainer_id
        trainer_link = row.find("a", href=re.compile(r"/trainer/\w+/"))
        if trainer_link:
            m = re.search(r"/trainer/(\w+)/", trainer_link["href"])
            entry["trainer_id"] = m.group(1) if m else None

        entries.append(entry)

    race_info["field_size"] = len(entries)
    return {"race": race_info, "entries": entries}
