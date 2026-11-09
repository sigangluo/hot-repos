"""GitHub Trending 页面的抓取与解析。

Trending 没有官方接口，只能解析网页。这里宁可报错也不静默产出错误数据：
页面不是 Trending 页、缺少必需字段、或"新增 Star"的时间词与所请求的时间段对不上，都抛出 TrendingError。
"""

import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote

from .. import config
from .client import GitHubClient

log = logging.getLogger(__name__)

_NAME = re.compile(r"^/([\w.-]+)/([\w.-]+)$")
_PERIOD_STARS = re.compile(r"([\d,]+)\s+stars?\s+(today|this week|this month)")
_COUNT = re.compile(r"\d[\d,]*")


class TrendingError(RuntimeError):
    """页面无法按预期解析，或请求失败。"""


@dataclass(frozen=True)
class Entry:
    full_name: str
    description: str | None
    language: str | None
    stars: int
    forks: int
    period_stars: int
    built_by: tuple[str, ...]


class _PageParser(HTMLParser):
    """逐个读取 `<article class="Box-row">`，每个对应榜单里的一个仓库。"""

    def __init__(self, since: str):
        super().__init__(convert_charrefs=True)
        self.since = since
        self.title = ""
        self.entries: list[Entry] = []
        self._in_title = False
        self._article: dict | None = None
        self._text: list[str] = []
        self._in_h2 = False
        self._capture: str | None = None  # 正在收集文字的字段
        self._capture_tag = ""
        self._capture_depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        classes = a.get("class", "").split()
        if tag == "title":
            self._in_title = True
        if tag == "article" and "Box-row" in classes:
            self._article = {"built_by": []}
            self._text = []
            return
        if self._article is None:
            return
        if self._capture:
            if tag == self._capture_tag:
                self._capture_depth += 1
            return
        href = a.get("href", "")
        if tag == "h2":
            self._in_h2 = True
        elif tag == "a" and self._in_h2 and "full_name" not in self._article:
            if match := _NAME.match(href):
                self._article["full_name"] = f"{match[1]}/{match[2]}"
        elif tag == "p" and "description" not in self._article:
            self._start_capture("description", tag)
        elif tag == "span" and a.get("itemprop") == "programmingLanguage":
            self._start_capture("language", tag)
        elif tag == "a" and href.endswith("/stargazers"):
            self._start_capture("stars", tag)
        elif tag == "a" and href.endswith(("/forks", "/network/members")):
            self._start_capture("forks", tag)
        elif tag == "img" and "avatar" in classes and a.get("alt", "").startswith("@"):
            self._article["built_by"].append(a["alt"][1:])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if self._article is None:
            return
        if self._capture and tag == self._capture_tag:
            self._capture_depth -= 1
            if self._capture_depth == 0:
                text = " ".join("".join(self._buffer).split())
                self._article[self._capture] = text
                self._capture = None
        elif tag == "h2":
            self._in_h2 = False
        elif tag == "article":
            self.entries.append(self._finish(self._article, "".join(self._text)))
            self._article = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._article is not None:
            self._text.append(data)
            if self._capture:
                self._buffer.append(data)

    def _start_capture(self, field: str, tag: str) -> None:
        self._capture, self._capture_tag, self._capture_depth, self._buffer = field, tag, 1, []

    def _finish(self, raw: dict, text: str) -> Entry:
        name = raw.get("full_name")
        if not name:
            raise TrendingError(f"第 {len(self.entries) + 1} 条没有找到仓库名，页面结构可能变了")

        def count(field: str) -> int:
            value = raw.get(field, "")
            if not _COUNT.fullmatch(value):
                raise TrendingError(f"{name}: 无法解析 {field}：{value!r}")
            return int(value.replace(",", ""))

        period = _PERIOD_STARS.search(text)
        if period is None:
            raise TrendingError(f"{name}: 没有找到新增 Star 数")
        expected = config.TRENDING_PERIODS[self.since]
        if period[2] != expected:
            raise TrendingError(f"{name}: 新增 Star 的时间词是「{period[2]}」，应为「{expected}」")
        return Entry(
            full_name=name,
            description=raw.get("description") or None,
            language=raw.get("language") or None,
            stars=count("stars"),
            forks=count("forks"),
            period_stars=int(period[1].replace(",", "")),
            built_by=tuple(raw["built_by"]),
        )


def parse_page(html: str, since: str) -> list[Entry]:
    """解析一页 Trending，按页面顺序返回；同一仓库重复出现时只保留第一次。"""
    if since not in config.TRENDING_PERIODS:
        raise ValueError(f"未知的时间段：{since}")
    parser = _PageParser(since)
    parser.feed(html)
    parser.close()
    if not parser.title.strip().startswith("Trending"):
        raise TrendingError(f"返回的不是 Trending 页面（标题：{parser.title.strip()[:60]!r}）")
    seen: set[str] = set()
    entries = []
    for entry in parser.entries:
        if entry.full_name.lower() in seen:
            log.warning("Trending 页面中 %s 重复出现，只保留第一次", entry.full_name)
            continue
        seen.add(entry.full_name.lower())
        entries.append(entry)
    return entries


def page_url(language: str) -> str:
    if language == config.TRENDING_ALL:
        return config.TRENDING_URL
    return f"{config.TRENDING_URL}/{quote(language, safe='')}"


async def fetch_page(client: GitHubClient, since: str, language: str) -> list[Entry]:
    """抓取并解析一个（时间段，语言）的榜单。"""
    url = page_url(language)
    response = await client.get(url, params={"since": since}, headers={"Accept": "text/html"})
    if response.status_code != 200:
        raise TrendingError(f"{url}?since={since} 返回 HTTP {response.status_code}")
    try:
        return parse_page(response.text, since)
    except TrendingError as e:
        raise TrendingError(f"{language}/{since}: {e}") from e
