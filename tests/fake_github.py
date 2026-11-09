"""内存中的假 GitHub：按真实接口的形状应答，用于不联网的流程测试。"""

import json
import re
from collections.abc import Callable

import httpx

from hot_repos import config

WEEK = 604800
FIRST_SUNDAY = 259200


def sunday(n: int) -> int:
    """第 n 个周日零点的时间戳（n 越大越新）。"""
    return FIRST_SUNDAY + (2900 + n) * WEEK


def blob(size: int) -> dict:
    return {"byteSize": size}


def make_node(name: str, stars: int, **changes) -> dict:
    node = {
        "nameWithOwner": name,
        "description": "desc",
        "homepageUrl": "",
        "createdAt": "2020-01-01T00:00:00Z",
        "pushedAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
        "isArchived": False,
        "isFork": False,
        "isTemplate": False,
        "diskUsage": 100,
        "stargazerCount": stars,
        "forkCount": 1,
        "owner": {"__typename": "Organization"},
        "watchers": {"totalCount": 2},
        "openIssues": {"totalCount": 3},
        "closedIssues": {"totalCount": 4},
        "openPRs": {"totalCount": 5},
        "mergedPRs": {"totalCount": 6},
        "primaryLanguage": {"name": "Python"},
        "languages": {"edges": [{"size": 900, "node": {"name": "Python"}}]},
        "repositoryTopics": {"nodes": [{"topic": {"name": "ai"}}]},
        "licenseInfo": {"spdxId": "MIT"},
        "defaultBranchRef": {"name": "main", "target": {"history": {"totalCount": 7}}},
        "releases": {"totalCount": 1},
        "latestRelease": {"tagName": "v1", "publishedAt": "2026-01-01T00:00:00Z"},
        "hasDiscussionsEnabled": False,
        "discussions": {"totalCount": 0},
        "fundingLinks": [],
        **{f"readme{i}": None for i in range(len(config.README_FILENAMES))},
    }
    node["readme0"] = blob(10)
    return node | changes


class FakeGitHub:
    """handler 可直接交给 httpx.MockTransport。`calls` 按路径类别统计请求数。"""

    def __init__(self, repos: dict[str, int], renames: dict[str, str] | None = None):
        self.repos = repos  # 当前名称 -> Star 数
        self.renames = renames or {}  # 旧名称 -> 当前名称
        self.calls: dict[str, int] = {}
        self.hidden: set[str] = set()  # 搜索能看到、但元数据查询返回 NOT_FOUND 的仓库
        self.history_weeks = 3
        self.hooks: dict[str, Callable[[httpx.Request], httpx.Response | None]] = {}

    def total_calls(self) -> int:
        return sum(self.calls.values())

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        kind = (
            "search"
            if path == "/search/repositories"
            else "graphql"
            if path == "/graphql"
            else path.rsplit("/", 1)[-1]
        )
        self.calls[kind] = self.calls.get(kind, 0) + 1
        if kind in self.hooks and (response := self.hooks[kind](request)):
            return response
        if kind == "search":
            return self.search(request)
        if kind == "graphql":
            return self.graphql(request)
        if kind == "contributors":
            return httpx.Response(
                200,
                json=[{"login": "x"}],
                headers={
                    "link": '<https://api.github.com/x?per_page=1&page=2>; rel="next", '
                    '<https://api.github.com/x?per_page=1&page=42>; rel="last"'
                },
            )
        if kind == "history":
            return self.history(request)
        return httpx.Response(404)

    def search(self, request):
        q = request.url.params["q"]
        if q.startswith("stars:>="):
            lower, upper = int(q.removeprefix("stars:>=")), 10**9
        else:
            lower, upper = map(int, q.removeprefix("stars:").split(".."))
        page = int(request.url.params["page"])
        names = [
            (n, s)
            for n, s in sorted(self.repos.items(), key=lambda x: (-x[1], x[0]))
            if lower <= s <= upper
        ]
        old = [
            (o, self.repos[c]) for o, c in self.renames.items() if lower <= self.repos[c] <= upper
        ]
        items = [
            {"full_name": n, "stargazers_count": s}
            for n, s in sorted(names + old, key=lambda x: (-x[1], x[0]))
        ]
        return httpx.Response(
            200, json={"incomplete_results": False, "items": items[(page - 1) * 100 : page * 100]}
        )

    def graphql(self, request):
        query = json.loads(request.content)["query"]
        data = {}
        for alias, owner, name in re.findall(
            r'(r\d+): repository\(owner: "([^"]+)", name: "([^"]+)"\)', query
        ):
            full = f"{owner}/{name}"
            current = self.renames.get(full, full)
            data[alias] = (
                make_node(current, self.repos[current])
                if current in self.repos and full not in self.hidden
                else None
            )
        errors = [{"type": "NOT_FOUND", "path": [a]} for a, v in data.items() if v is None]
        body = {"data": data} | ({"errors": errors} if errors else {})
        return httpx.Response(200, json=body)

    def history(self, request):
        page = int(request.url.params["page"])
        per_page = config.STAR_WEEKS_PER_PAGE
        total_weeks = self.history_weeks
        newest_first = [
            {"week": sunday(total_weeks - i), "total": 7, "days": [1] * 7}
            for i in range(total_weeks)
        ]
        rows = newest_first[(page - 1) * per_page : page * per_page]
        pages = max(1, -(-total_weeks // per_page))
        link = f'<https://api.github.com/x?page={pages}>; rel="last"' if pages > 1 else ""
        return httpx.Response(200, json=rows, headers={"link": link} if link else {})
