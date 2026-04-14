"""馬プロフィール（血統・性別・生年月日）取得"""
import re
from datetime import date
from typing import Any
from loguru import logger
from bs4 import BeautifulSoup
from scraper.base import RateLimitedSession


def fetch_horse_profile(
    session: RateLimitedSession, horse_id: str
) -> dict[str, Any] | None:
    """
    returns: {
        "horse": {...},      # horses テーブル用
        "stallions": [...],  # stallions テーブル用（父・母・母父）
    }
    """
    url = f"https://db.netkeiba.com/horse/{horse_id}/"
    try:
        resp = session.get(url, encoding="euc-jp")
    except Exception as e:
        logger.warning(f"horse_profile fetch failed for {horse_id}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    horse: dict[str, Any] = {"horse_id": horse_id}
    stallions: list[dict[str, str]] = []

    # 馬名
    name_tag = soup.find("div", class_="horse_title") or soup.find("h1", class_="horse_name")
    if name_tag:
        horse["name"] = name_tag.find("h1").get_text(strip=True) if name_tag.find("h1") else name_tag.get_text(strip=True)
    else:
        title = soup.find("title")
        horse["name"] = title.get_text(strip=True).split("|")[0].strip() if title else horse_id

    # プロフィール表
    prof_table = soup.find("table", class_="db_prof_table")
    if prof_table:
        for row in prof_table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not (th and td):
                continue
            label = th.get_text(strip=True)
            value = td.get_text(strip=True)

            if "生年月日" in label:
                m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
                if m:
                    horse["birth_date"] = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif "性別" in label or "性齢" in label:
                if "牡" in value:
                    horse["sex"] = "牡"
                elif "牝" in value:
                    horse["sex"] = "牝"
                elif "セン" in value:
                    horse["sex"] = "セン"
            elif "調教師" in label:
                trainer_link = td.find("a", href=re.compile(r"/trainer/"))
                if trainer_link:
                    m = re.search(r"/trainer/(\w+)/", trainer_link["href"])
                    if m:
                        horse["trainer_id"] = m.group(1)

    # 血統表（父・母・母父）
    blood_table = soup.find("table", class_="blood_table")
    if blood_table:
        links = blood_table.find_all("a", href=re.compile(r"/horse/(\d+)/"))
        positions = ["sire_id", "dam_id", "broodmare_sire_id"]
        for i, link in enumerate(links[:3]):
            m = re.search(r"/horse/(\d+)/", link["href"])
            if m:
                sid = m.group(1)
                horse[positions[i]] = sid
                stallions.append({"horse_id": sid, "name": link.get_text(strip=True)})

    return {"horse": horse, "stallions": stallions}
