"""官方周 Star 分布（REST）。

接口按周返回仍保留的 Star 数及逐日计数，新的在前，每页最多 30 周。
已取消或被清理的 Star 不在其中，不能据此还原历史净增长。
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .. import config
from ..cache import Fetched, Journal
from ..collect import collect
from .client import GitHubClient, GitHubError

LAST_PAGE = re.compile(r'[?&]page=(\d+)>; rel="last"')
WEEK_SECONDS = 7 * 24 * 3600
SUNDAY_OFFSET = 3 * 24 * 3600  # 1970-01-01 是周四，第一个周日零点为 1970-01-04


@dataclass(frozen=True)
class StarWeeks:
    """一个仓库已抓取的周分布。`weeks` 按周起点升序。"""

    weeks: list[dict[str, Any]]  # 每项含 week_start、stars、days
    pages_fetched: int
    pages_total: int
    fetched_at: datetime


def validate_page(rows: Any) -> list[dict]:
    """检查一页数据的形状；不合法时抛出 ValueError，避免把异常数据写入缓存。"""
    if not isinstance(rows, list) or len(rows) > config.STAR_WEEKS_PER_PAGE:
        raise ValueError(f"每页最多 {config.STAR_WEEKS_PER_PAGE} 周")
    for row in rows:
        week, total, days = row.get("week"), row.get("total"), row.get("days")
        if not isinstance(week, int) or week <= 0 or week % WEEK_SECONDS != SUNDAY_OFFSET:
            raise ValueError(f"周起点应为 UTC 周日零点: {week}")
        if not isinstance(total, int) or total < 0:
            raise ValueError("周 Star 数应为非负整数")
        if not isinstance(days, list) or len(days) != 7:
            raise ValueError("逐日计数应为 7 项")
        if any(type(d) is not int or d < 0 for d in days) or sum(days) != total:
            raise ValueError("逐日计数应为非负整数，且之和等于周合计")
    starts = [row["week"] for row in rows]
    if starts != sorted(set(starts), reverse=True):
        raise ValueError("周应唯一且按时间从新到旧排列")
    return rows


def last_page(link: str | None) -> int:
    match = LAST_PAGE.search(link or "")
    if match:
        return int(match.group(1))
    if 'rel="next"' in (link or ""):
        raise ValueError("分页响应缺少最后一页的链接")
    return 1


async def fetch_page(client: GitHubClient, full_name: str, page: int) -> dict | None:
    """取一页；仓库不存在时返回 None。"""
    response = await client.get(
        f"{config.GITHUB_REST_URL}/repos/{full_name}/stargazers/history",
        params={"per_page": config.STAR_WEEKS_PER_PAGE, "page": page},
        headers={"X-GitHub-Api-Version": config.STAR_WEEKS_API_VERSION},
        retry_statuses=(202,),  # 202 表示服务端正在生成统计
        expect_json=True,
    )
    if response.status_code in (404, 409, 451):  # 不存在、空仓库、因法律原因不可访问
        return None
    response.raise_for_status()
    try:
        weeks = validate_page(response.json())
        pages = last_page(response.headers.get("link"))
    except ValueError as e:
        raise GitHubError(f"{full_name} 第 {page} 页数据异常：{e}") from e
    return {"weeks": weeks, "last_page": pages}


def _page_key(name: str, page: int, anchor: int) -> str:
    # 新的一周开始后，各页内容整体后移。后续页的键带上第一页最新周的时间戳，旧缓存自然失效。
    return f"{name}#1" if page == 1 else f"{name}#{page}@{anchor}"


async def fetch_star_weeks(
    client: GitHubClient,
    names: list[str],
    journal: Journal,
    max_age: timedelta,
    *,
    full: bool,
    now: datetime | None = None,
) -> dict[str, StarWeeks | None]:
    """`full=False` 只取最近一页；`full=True` 向创建时间回溯取全部页。仓库不存在时结果为 None。"""

    async def worker(batch: list[str]) -> dict[str, Any]:
        return {key: await fetch_page(client, key.removesuffix("#1"), 1) for key in batch}

    first = await collect(
        [f"{n}#1" for n in names],
        journal,
        max_age,
        worker,
        label="周 Star 分布（第 1 页）",
        concurrency=config.REST_CONCURRENCY,
        now=now,
    )

    pages: dict[str, list[Fetched]] = {n: [first[f"{n}#1"]] for n in names}
    if full:
        wanted: dict[str, tuple[str, int]] = {}
        for n in names:
            head = first[f"{n}#1"].value
            if head is None:
                continue
            anchor = head["weeks"][0]["week"] if head["weeks"] else 0
            for page in range(2, head["last_page"] + 1):
                wanted[_page_key(n, page, anchor)] = (n, page)

        async def later(batch: list[str]) -> dict[str, Any]:
            return {key: await fetch_page(client, *wanted[key]) for key in batch}

        rest = await collect(
            list(wanted),
            journal,
            max_age,
            later,
            label="周 Star 分布（后续页）",
            concurrency=config.REST_CONCURRENCY,
            now=now,
        )
        for key, (n, _) in wanted.items():
            pages[n].append(rest[key])

    return {n: _assemble(n, parts) for n, parts in pages.items()}


def _assemble(name: str, parts: list[Fetched]) -> StarWeeks | None:
    if parts[0].value is None or any(p.value is None for p in parts):
        return None
    starts = [w["week"] for p in parts for w in p.value["weeks"]]
    if any(a - b != WEEK_SECONDS for a, b in zip(starts, starts[1:], strict=False)):
        raise GitHubError(f"{name} 的周分布不连续，周边界可能已变化；请使用 --refresh 重抓")
    weeks = [
        {
            "week_start": datetime.fromtimestamp(w["week"], UTC).date(),
            "stars": w["total"],
            "days": w["days"],
        }
        for p in reversed(parts)
        for w in reversed(p.value["weeks"])
    ]
    return StarWeeks(weeks, len(parts), parts[0].value["last_page"], parts[0].fetched_at)
