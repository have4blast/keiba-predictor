"""レートリミット付きHTTPセッション + フォールバックパーサーヘルパー"""
import os
import time
import random
from typing import TYPE_CHECKING

import requests
from loguru import logger
from dotenv import load_dotenv

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

load_dotenv()

_DELAY_MIN = float(os.getenv("SCRAPE_DELAY_MIN", "2.0"))
_DELAY_MAX = float(os.getenv("SCRAPE_DELAY_MAX", "3.5"))
_USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)


class RateLimitedSession:
    """2〜3.5秒のランダム遅延とリトライ機能を持つHTTPセッション"""

    def __init__(
        self,
        delay_min: float = _DELAY_MIN,
        delay_max: float = _DELAY_MAX,
        user_agent: str = _USER_AGENT,
        max_retries: int = 3,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries

    def get(self, url: str, encoding: str | None = None, **kwargs) -> requests.Response:
        """レートリミット・リトライ付きGETリクエスト"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, timeout=30, **kwargs)
                resp.raise_for_status()
                if encoding:
                    resp.encoding = encoding
                return resp
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (404, 403):
                    raise  # リトライ不要
                wait = 2 ** (attempt + 1)
                logger.warning(f"HTTP error attempt {attempt+1}/{self.max_retries}: {e} — retrying in {wait}s")
                time.sleep(wait)
            except requests.exceptions.RequestException as e:
                wait = 2 ** (attempt + 1)
                logger.warning(f"Request error attempt {attempt+1}/{self.max_retries}: {e} — retrying in {wait}s")
                time.sleep(wait)

        raise RuntimeError(f"Max retries exceeded for {url}")


def try_selectors(soup: "BeautifulSoup", selectors: list[str]) -> "Tag | None":
    """
    複数の CSS セレクタを順番に試み、最初にヒットした要素を返す。

    HTML 構造変更に対する耐性を持たせるためのフォールバック機構。
    全て失敗した場合は None を返す。
    """
    for sel in selectors:
        el = soup.select_one(sel)
        if el is not None:
            logger.debug(f"セレクタ使用: {sel!r}")
            return el
    logger.warning(f"全セレクタ失敗: {selectors}")
    return None
