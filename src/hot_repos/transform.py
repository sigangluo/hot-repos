"""API 响应 → 规范数据行。纯函数，不做网络和文件操作。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .github.graphql import readme_path


def parse_time(value: str | None) -> datetime | None:
    """ISO 8601 字符串 → 带时区的时间；空值为 None。"""
    return datetime.fromisoformat(value) if value else None


def blank_to_none(value: str | None) -> str | None:
    """GitHub 用空字符串表示"未填写"，统一为 None。"""
    return value or None


@dataclass(frozen=True)
class Group:
    """指向同一个当前仓库的一组查询名。"""

    node: dict[str, Any]  # 获取时间最新的元数据节点
    query_names: list[str]  # 榜单中出现过的名称（改名前后），按字母序
    fetched_at: datetime  # node 的获取时间


def canonical_groups(nodes: dict[str, dict], fetched_at: dict[str, datetime]) -> list[Group]:
    """把指向同一个当前仓库的查询名（仓库改名前后）合并为一组。"""
    by_current: dict[str, list[str]] = {}
    for name, node in nodes.items():
        by_current.setdefault(node["nameWithOwner"].lower(), []).append(name)
    groups = []
    for names in by_current.values():
        names.sort()
        freshest = max(names, key=lambda n: fetched_at[n])
        groups.append(Group(nodes[freshest], names, fetched_at[freshest]))
    return groups


def repo_row(node: dict[str, Any], contributors: int | None) -> dict[str, Any]:
    """GraphQL 节点 → `repos` 表的一行（不含名次、获取时间和 star_weeks_* 各列）。"""
    commit = ((node.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {}
    release = node.get("latestRelease") or {}
    return {
        "full_name": node["nameWithOwner"],
        "description": blank_to_none(node["description"]),
        "homepage": blank_to_none(node["homepageUrl"]),
        "owner_type": node["owner"]["__typename"],
        "created_at": parse_time(node["createdAt"]),
        "pushed_at": parse_time(node["pushedAt"]),
        "updated_at": parse_time(node["updatedAt"]),
        "is_archived": node["isArchived"],
        "is_fork": node["isFork"],
        "is_template": node["isTemplate"],
        "disk_usage_kb": node["diskUsage"],
        "stars": node["stargazerCount"],
        "forks": node["forkCount"],
        "watchers": node["watchers"]["totalCount"],
        "open_issues": node["openIssues"]["totalCount"],
        "closed_issues": node["closedIssues"]["totalCount"],
        "open_prs": node["openPRs"]["totalCount"],
        "merged_prs": node["mergedPRs"]["totalCount"],
        "discussions_enabled": node["hasDiscussionsEnabled"],
        "discussions": node["discussions"]["totalCount"],
        "primary_language": (node["primaryLanguage"] or {}).get("name"),
        "languages": [
            {"name": e["node"]["name"], "bytes": e["size"]}
            for e in node["languages"]["edges"] or []
        ],
        "topics": [t["topic"]["name"] for t in node["repositoryTopics"]["nodes"]],
        "license": (node["licenseInfo"] or {}).get("spdxId"),
        "default_branch": (node.get("defaultBranchRef") or {}).get("name"),
        "commit_count": commit.get("totalCount"),
        "contributors": contributors,
        "release_count": node["releases"]["totalCount"],
        "latest_release_tag": release.get("tagName"),
        "latest_release_at": parse_time(release.get("publishedAt")),
        "funding": [{"platform": f["platform"], "url": f["url"]} for f in node["fundingLinks"]],
        "readme_path": readme_path(node),
    }
