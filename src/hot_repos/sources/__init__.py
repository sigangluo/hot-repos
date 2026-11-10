"""外部分类体系的来源。

每个来源模块把别人已经做好的公开分类整理成统一的 `Collected`：体系定义（节点、说明）加上
“来源里的项目 → 它所属的节点”。这里只做取数与解析，不判断分类；匹配总榜、写文件、校验都在 `sync.py`。
新增一个来源：加一个模块，提供 `collect(fetcher) -> Collected`，再登记到 `registry()`。
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "hot-repos (+https://github.com/sigangluo/hot-repos)"
RETRY_STATUS = (429, 500, 502, 503, 504)


class SourceError(RuntimeError):
    """来源取不到，或内容不是预期的格式。已有的体系数据保持原样。"""


@dataclass(frozen=True)
class Collected:
    """一个来源整理后的内容。

    `meta` 是 scheme.json 的内容，不含 `as_of`（同步时填入）；`nodes` 是来源里出现的全部分类，
    父节点排在子节点之前，编号规则见 docs/data-model.md。`members` 的键是来源里的 `owner/repo`
    （大小写、旧名都按来源原样），值是它所属的节点编号；体系有主分类（`primary`）时第一个是主分类。
    """

    meta: dict[str, Any]
    members: dict[str, list[str]]


class Fetcher:
    """带重试的 HTTP 取数。GitHub 接口请求带上 Token（若有），其余来源不带。"""

    def __init__(
        self,
        token: str | None = None,
        client: httpx.Client | None = None,
        *,
        attempts: int = 4,
        pause: float = 2.0,
    ) -> None:
        self.token = token
        self.client = client or httpx.Client(timeout=60, follow_redirects=True)
        self.attempts = attempts
        self.pause = pause

    def text(self, url: str) -> str:
        return self._get(url).text

    def json(self, url: str) -> Any:
        return self._get(url).json()

    def texts(self, urls: list[str], workers: int = 8) -> list[str]:
        """并发取一批文本，结果顺序与 urls 一致。"""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(self.text, urls))

    def _get(self, url: str) -> httpx.Response:
        headers = {"User-Agent": USER_AGENT}
        if self.token and urlparse(url).hostname == "api.github.com":
            headers["Authorization"] = f"Bearer {self.token}"
        last = "未知错误"
        for attempt in range(self.attempts):
            if attempt:
                time.sleep(self.pause * 2 ** (attempt - 1))
            try:
                response = self.client.get(url, headers=headers)
            except httpx.TransportError as e:
                last = str(e) or type(e).__name__
                continue
            if response.status_code == 200:
                return response
            last = f"HTTP {response.status_code}"
            if response.status_code not in RETRY_STATUS:
                break
        raise SourceError(f"取不到 {url}：{last}")


Collector = Callable[[Fetcher], Collected]


def registry() -> dict[str, Collector]:
    """全部来源，键就是体系编号。"""
    from . import borges, explore, landscape, ossinsight

    return {
        "explore": explore.collect,
        "ossinsight": ossinsight.collect,
        "borges": borges.collect,
        "cncf": landscape.collect_cncf,
        "lfai": landscape.collect_lfai,
    }
