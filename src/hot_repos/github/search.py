"""总榜搜索：按 Star 数降序取前 N 个仓库。

搜索接口单次查询最多返回 1000 条。这里把 Star 数从高到低切成若干区间，
每个区间最多取 900 条；区间边界上 Star 数相同的项目留到下一个区间重新查询，最后按仓库名去重。
搜索结果持续变化，因此得到的是一次采集快照，不是事务一致的时点排名。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .. import cache, config
from .client import GitHubClient, GitHubError

log = logging.getLogger(__name__)

SEARCH_URL = f"{config.GITHUB_REST_URL}/search/repositories"
MAX_PAGES = config.SEARCH_SHARD_LIMIT // config.SEARCH_PAGE_SIZE


@dataclass(frozen=True)
class Board:
    """总榜：按名次排列的 `(仓库名, Star 数)`，及采集时间。"""

    items: list[tuple[str, int]]
    captured_at: datetime


async def top_by_stars(
    client: GitHubClient, n: int, cache_dir: Path, max_age: timedelta, now: datetime | None = None
) -> Board:
    now = now or cache.utcnow()
    final = cache_dir / f"search_{n}.json"
    cached = cache.load_stamped(final)
    if cached and cached.is_fresh(max_age, now) and len(cached.value) == n:
        log.info("总榜：命中缓存（%d 个）", n)
        return Board([(name, stars) for name, stars in cached.value], cached.fetched_at)

    progress_path = cache_dir / f"search_{n}_progress.json"
    progress = cache.load_stamped(progress_path)
    if progress and not progress.is_fresh(max_age, now):
        progress = None
    found = (
        {name.lower(): (name, stars) for name, stars in progress.value["items"]} if progress else {}
    )
    upper: int | None = progress.value["upper"] if progress else None
    started_at = progress.fetched_at if progress else now

    while len(found) < n:
        floor = config.SEARCH_STAR_FLOOR
        query = f"stars:>={floor}" if upper is None else f"stars:{min(floor, upper // 2)}..{upper}"
        shard = await _read_shard(client, query, limit=n - len(found))
        if not shard:
            raise GitHubError(f"搜索提前结束，只得到 {len(found)}/{n} 个仓库")
        boundary = shard[-1][1]
        exhausted = len(shard) < config.SEARCH_SHARD_LIMIT
        # 未取完的区间里，边界 Star 数上的项目可能不全，留到下一区间重新查询。
        enough = len(found) + len(shard) >= n
        for name, stars in shard:
            if exhausted or enough or stars > boundary:
                found[name.lower()] = (name, stars)
        log.info("总榜：%d/%d，当前边界 %d Star", min(len(found), n), n, boundary)
        if upper == boundary and not exhausted:
            raise GitHubError(f"Star 数为 {boundary} 的项目超过一个区间的容量，需要更细的划分")
        upper = boundary - 1 if exhausted else boundary
        cache.save_stamped(
            progress_path, {"upper": upper, "items": list(found.values())}, started_at
        )

    items = sorted(found.values(), key=lambda x: (-x[1], x[0].lower()))[:n]
    cache.save_stamped(final, items, started_at)
    progress_path.unlink(missing_ok=True)
    return Board(items, started_at)


async def _read_shard(client: GitHubClient, query: str, *, limit: int) -> list[tuple[str, int]]:
    shard: list[tuple[str, int]] = []
    for page in range(1, MAX_PAGES + 1):
        data = await _search_page(client, query, page)
        items = data["items"]
        shard.extend((it["full_name"], it["stargazers_count"]) for it in items)
        log.info("搜索 %s 第 %d 页：%d 个", query, page, len(items))
        if len(items) < config.SEARCH_PAGE_SIZE or len(shard) >= limit:
            break
    return shard


async def _search_page(client: GitHubClient, query: str, page: int) -> dict:
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": config.SEARCH_PAGE_SIZE,
        "page": page,
    }
    for attempt in range(4):
        response = await client.get(
            SEARCH_URL, params=params, extra_pacer=client.search_pacer, expect_json=True
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("incomplete_results"):
            return data
        await client.sleep(2**attempt)
    raise GitHubError(f"GitHub 搜索结果不完整：{query} 第 {page} 页，请稍后重跑")
