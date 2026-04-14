"""レース結果詳細スクレイピング（着順・タイム・上がり3F・ラップ・脚質）"""
import json
import re
from datetime import date
from typing import Any
from loguru import logger
from bs4 import BeautifulSoup
from scraper.base import RateLimitedSession


def _parse_time(time_str: str) -> float | None:
    """'1:34.5' → 94.5 秒"""
    time_str = time_str.strip()
    if not time_str or time_str in ("---", ""):
        return None
    m = re.match(r"(?:(\d+):)?(\d+)\.(\d+)", time_str)
    if not m:
        return None
    minutes = int(m.group(1) or 0)
    seconds = int(m.group(2))
    tenths  = int(m.group(3))
    return minutes * 60 + seconds + tenths / 10


def _parse_weight(weight_str: str) -> tuple[int | None, int | None]:
    """'520(+4)' → (520, 4)  /  '計不' → (None, None)"""
    weight_str = weight_str.strip()
    m = re.match(r"(\d+)\(([+-]?\d+)\)", weight_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_corner_positions(corner_str: str) -> list[int | None]:
    """'1-2-2-3' → [1, 2, 2, 3]"""
    parts = re.split(r"[-\s]+", corner_str.strip())
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(None)
    return result


def _infer_running_style(corner_positions: list[int | None], field_size: int) -> str | None:
    """コーナー通過順位から脚質を推定"""
    valid = [p for p in corner_positions if p is not None]
    if not valid or field_size == 0:
        return None
    avg = sum(valid) / len(valid)
    ratio = avg / max(field_size, 1)
    if ratio <= 0.15:
        return "逃"
    elif ratio <= 0.35:
        return "先"
    elif ratio <= 0.6:
        return "差"
    else:
        return "追"


def fetch_race_detail(
    session: RateLimitedSession, race_id: str
) -> dict[str, Any] | None:
    """
    race_id: 12桁のレースID
    returns: {
        "race": {...},        # races テーブル用
        "entries": [...],     # race_entries テーブル用
    }
    """
    url = f"https://db.netkeiba.com/race/{race_id}/"
    try:
        resp = session.get(url, encoding="euc-jp")
    except Exception as e:
        logger.warning(f"race_detail fetch failed for {race_id}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # ── レース基本情報 ──────────────────────────────────────
    race_info: dict[str, Any] = {"race_id": race_id}

    # 日付・競馬場（race_id から推定: YYYYMMDD + 開催場コード2桁 + 回 + 日 + レース番号）
    year  = race_id[:4]
    month = race_id[4:6]
    day   = race_id[6:8]
    race_info["date"] = date(int(year), int(month), int(day))

    # 会場コードマッピング
    venue_map = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }
    venue_code = race_id[8:10]
    race_info["venue"] = venue_map.get(venue_code, venue_code)

    # レース情報テキスト（距離・馬場・天候・馬場状態）
    race_data01 = soup.find("div", class_="RaceData01")
    if race_data01:
        text = race_data01.get_text()
        # 距離と馬場
        m = re.search(r"(芝|ダート|障害)\s*(\d+)m", text)
        if m:
            race_info["surface"]  = m.group(1)
            race_info["distance"] = int(m.group(2))
        # 天候
        m = re.search(r"天候\s*:\s*(\S+)", text)
        if m:
            race_info["weather"] = m.group(1)
        # 馬場
        m = re.search(r"馬場\s*:\s*(\S+)", text)
        if m:
            race_info["going"] = m.group(1)

    # グレード
    grade_tag = soup.find("span", class_=re.compile(r"Icon_GradeType"))
    if grade_tag:
        race_info["grade"] = grade_tag.get_text(strip=True)

    # ラップタイム
    lap_table = soup.find("table", class_="race_lap_cell")
    lap_times: list[float] = []
    if lap_table:
        for td in lap_table.find_all("td"):
            try:
                lap_times.append(float(td.get_text(strip=True)))
            except ValueError:
                pass
    if lap_times:
        race_info["lap_times"] = json.dumps(lap_times)

    # ── 出走・結果テーブル ────────────────────────────────────
    result_table = soup.find("table", class_=re.compile(r"race_table_01"))
    entries: list[dict[str, Any]] = []

    if not result_table:
        logger.warning(f"Result table not found for race {race_id}")
        return {"race": race_info, "entries": []}

    headers: list[str] = []
    for th in result_table.find_all("th"):
        headers.append(th.get_text(strip=True))

    rows = result_table.find_all("tr")[1:]  # ヘッダー除く
    field_size = len(rows)
    race_info["field_size"] = field_size

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 10:
            continue

        entry: dict[str, Any] = {"race_id": race_id}

        # 着順
        try:
            entry["finish_position"] = int(cols[0].get_text(strip=True))
        except ValueError:
            entry["finish_position"] = None  # 除外等

        # 枠番
        try:
            entry["post_position"] = int(cols[1].get_text(strip=True))
        except ValueError:
            entry["post_position"] = None

        # 馬名リンク → horse_id
        horse_link = cols[3].find("a", href=re.compile(r"/horse/(\d+)"))
        if horse_link:
            m = re.search(r"/horse/(\d+)", horse_link["href"])
            entry["horse_id"] = m.group(1) if m else None
        else:
            entry["horse_id"] = None

        if not entry["horse_id"]:
            continue

        # 斤量
        try:
            entry["handicap_weight"] = float(cols[5].get_text(strip=True))
        except (ValueError, IndexError):
            entry["handicap_weight"] = None

        # 騎手リンク → jockey_id
        jockey_link = cols[6].find("a", href=re.compile(r"/jockey/(\w+)"))
        if jockey_link:
            m = re.search(r"/jockey/(\w+)/", jockey_link["href"])
            entry["jockey_id"] = m.group(1) if m else None

        # タイム
        entry["time"] = _parse_time(cols[7].get_text(strip=True))

        # 単勝オッズ
        try:
            entry["win_odds"] = float(cols[10].get_text(strip=True))
        except (ValueError, IndexError):
            entry["win_odds"] = None

        # 馬体重
        weight_str = cols[14].get_text(strip=True) if len(cols) > 14 else ""
        w, wd = _parse_weight(weight_str)
        entry["horse_weight"] = w
        entry["weight_diff"]  = wd

        # 調教師リンク → trainer_id
        if len(cols) > 15:
            trainer_link = cols[15].find("a", href=re.compile(r"/trainer/(\w+)"))
            if trainer_link:
                m = re.search(r"/trainer/(\w+)/", trainer_link["href"])
                entry["trainer_id"] = m.group(1) if m else None

        # コーナー通過順位
        if len(cols) > 11:
            corner_str = cols[11].get_text(strip=True)
            if corner_str and corner_str != "---":
                positions = _parse_corner_positions(corner_str)
                entry["corner_positions"] = json.dumps(positions)
                entry["running_style"] = _infer_running_style(positions, field_size)

        entries.append(entry)

    # 上がり3Fタイムは別テーブルから取得（race_table_01の最後列）
    for i, row in enumerate(rows):
        cols = row.find_all("td")
        if len(cols) > 12 and i < len(entries):
            try:
                entries[i]["last_3f_time"] = float(cols[12].get_text(strip=True))
            except (ValueError, IndexError):
                entries[i]["last_3f_time"] = None

    return {"race": race_info, "entries": entries}
