"""オッズ取得（単勝・馬連・3連複・変動履歴）"""
import json
from datetime import datetime
from typing import Any
from loguru import logger
from scraper.base import RateLimitedSession


def fetch_odds(
    session: RateLimitedSession, race_id: str
) -> dict[str, Any] | None:
    """
    returns: {
        "win":      {horse_id: odds, ...},
        "quinella": [(horse_a, horse_b, odds), ...],
        "trifecta": [(h1, h2, h3, odds), ...],
        "timestamp": datetime,
    }
    """
    url = (
        f"https://race.netkeiba.com/api/api_get_odds_3wf.html"
        f"?race_id={race_id}&type=b1"
    )
    try:
        resp = session.get(url, encoding="utf-8")
    except Exception as e:
        logger.warning(f"odds fetch failed for {race_id}: {e}")
        return None

    try:
        data = resp.json()
    except Exception:
        logger.warning(f"odds JSON parse failed for {race_id}")
        return None

    result: dict[str, Any] = {
        "timestamp": datetime.utcnow(),
        "win": {},
        "quinella": [],
        "trifecta": [],
    }

    # 単勝オッズ
    odds_list = data.get("data", {}).get("Odds", {}).get("Win", [])
    for item in odds_list:
        horse_num = item.get("HorseNum")
        odds_val  = item.get("Odds")
        if horse_num and odds_val:
            result["win"][str(horse_num)] = float(odds_val)

    # 馬連オッズ（最大20件）
    quinella_list = data.get("data", {}).get("Odds", {}).get("Quinella", [])
    for item in quinella_list[:20]:
        nums = item.get("HorseNums", [])
        odds_val = item.get("Odds")
        if len(nums) == 2 and odds_val:
            result["quinella"].append((nums[0], nums[1], float(odds_val)))

    # 3連複オッズ（最大20件）
    trifecta_list = data.get("data", {}).get("Odds", {}).get("Trio", [])
    for item in trifecta_list[:20]:
        nums = item.get("HorseNums", [])
        odds_val = item.get("Odds")
        if len(nums) == 3 and odds_val:
            result["trifecta"].append((nums[0], nums[1], nums[2], float(odds_val)))

    return result
