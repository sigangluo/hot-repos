"""贡献者数量（REST）。"""

import re
from datetime import datetime, timedelta

from .. import config
from ..cache import Fetched, Journal
from ..collect import collect
from .client import GitHubClient

LAST_PAGE = re.compile(r'[?&]page=(\d+)>; rel="last"')


async def count_contributors(client: GitHubClient, full_name: str) -> int | None:
    """每页取 1 条，用分页链接里的最后一页页码作为总数（含匿名贡献者）。

    GitHub 对超大仓库不提供贡献者列表（403 "too large"），此时返回 None。
    """
    response = await client.get(
        f"{config.GITHUB_REST_URL}/repos/{full_name}/contributors",
        params={"per_page": 1, "anon": 1},
        expect_json=True,
    )
    # 204 无内容；404 不存在；409 空仓库；451 因法律原因不可访问。
    if response.status_code in (204, 404, 409, 451) or (
        response.status_code == 403 and "too large" in response.text.lower()
    ):
        return None
    response.raise_for_status()
    match = LAST_PAGE.search(response.headers.get("link", ""))
    return int(match.group(1)) if match else len(response.json())


async def fetch_counts(
    client: GitHubClient,
    names: list[str],
    journal: Journal,
    max_age: timedelta,
    *,
    now: datetime | None = None,
) -> dict[str, Fetched]:
    async def worker(batch: list[str]) -> dict[str, int | None]:
        return {name: await count_contributors(client, name) for name in batch}

    return await collect(
        names,
        journal,
        max_age,
        worker,
        label="贡献者数",
        concurrency=config.REST_CONCURRENCY,
        now=now,
    )
