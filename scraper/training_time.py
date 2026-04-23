"""調教タイムスクレイパー

netkeiba.com の馬ページ「調教」タブから最終追い切りデータを取得する。
取得元: https://db.netkeiba.com/horse/yyyynnnnnnn/#tab_training
"""
import re
from datetime import date, datetime
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

from scraper.base import RateLimitedSession, try_selectors


_COURSE_MAP = {
    "坂": "坂路", "ウ": "ウッド", "芝": "芝", "ダ": "ダート",
    "プ": "プール", "障": "障害コース",
}

_GEAR_KEYWORDS = {
    "一杯": "一杯", "強め": "強め", "馬なり": "馬なり",
    "手前": "手前変換", "仕掛": "仕掛け",
}


def _parse_time(time_str: str) -> float | None:
    """'52.3' or '1:52.3' 形式を秒数に変換する"""
    if not time_str:
        return None
    time_str = time_str.strip()
    m = re.match(r"(\d+):(\d+\.\d+)", time_str)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    try:
        return float(time_str)
    except ValueError:
        return None


def _parse_course(course_str: str) -> str | None:
    """'坂路', 'ウッドチップ' 等の略称を正規化する"""
    for abbr, full in _COURSE_MAP.items():
        if abbr in course_str:
            return full
    return course_str.strip() or None


def _parse_gear(note_str: str) -> str | None:
    """調教備考から強度を抽出する"""
    for kw, label in _GEAR_KEYWORDS.items():
        if kw in note_str:
            return label
    return None


def fetch_training_times(
    session: RateLimitedSession,
    horse_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    馬の直近の調教タイム履歴を取得する。

    returns: [
        {
            "horse_id":   str,
            "date":       date,
            "course":     str | None,
            "total_time": float | None,  # 秒
            "last_f_time":float | None,  # 秒
            "gear":       str | None,
        },
        ...
    ]
    """
    url = f"https://db.netkeiba.com/horse/{horse_id}/"
    try:
        resp = session.get(url, encoding="euc-jp")
    except Exception as e:
        logger.warning(f"training_time fetch failed for {horse_id}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    # 調教テーブルを複数セレクタで探す
    table = try_selectors(soup, [
        "table.training_table",
        "div#tab_training table",
        "div.training_wrap table",
        "table.b_training",
    ])

    if table is None:
        logger.debug(f"調教テーブルなし: horse_id={horse_id}")
        return []

    results: list[dict[str, Any]] = []
    rows = table.find_all("tr")[1:]  # ヘッダー除く

    for row in rows[:limit]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 4:
            continue

        # 列構成の推定（日付 / コース / タイム / 上がり / 備考）
        date_str   = cells[0] if len(cells) > 0 else ""
        course_str = cells[1] if len(cells) > 1 else ""
        time_str   = cells[2] if len(cells) > 2 else ""
        last_f_str = cells[3] if len(cells) > 3 else ""
        note_str   = cells[4] if len(cells) > 4 else ""

        # 日付パース
        try:
            parsed_date: date | None = datetime.strptime(
                re.sub(r"[年月]", "-", date_str).replace("日", ""), "%Y-%m-%d"
            ).date()
        except ValueError:
            parsed_date = None

        if parsed_date is None:
            continue

        results.append({
            "horse_id":    horse_id,
            "date":        parsed_date,
            "course":      _parse_course(course_str),
            "total_time":  _parse_time(time_str),
            "last_f_time": _parse_time(last_f_str),
            "gear":        _parse_gear(note_str),
        })

    logger.debug(f"調教タイム取得: horse_id={horse_id}, 件数={len(results)}")
    return results
