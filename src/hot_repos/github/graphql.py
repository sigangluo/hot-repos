"""批量查询仓库元数据（GraphQL）。"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from .. import config
from ..cache import Fetched, Journal
from ..collect import collect
from .client import GitHubClient, GitHubError

log = logging.getLogger(__name__)

# README 只记录各候选文件名是否存在（有内容），不下载正文。
_README_FIELDS = "\n".join(
    f'  readme{i}: object(expression: "HEAD:{name}") {{ ... on Blob {{ byteSize }} }}'
    for i, name in enumerate(config.README_FILENAMES)
)

FIELDS = (
    """
  nameWithOwner description homepageUrl createdAt pushedAt updatedAt
  isArchived isFork isTemplate diskUsage stargazerCount forkCount
  owner { __typename }
  watchers { totalCount }
  openIssues: issues(states: OPEN) { totalCount }
  closedIssues: issues(states: CLOSED) { totalCount }
  openPRs: pullRequests(states: OPEN) { totalCount }
  mergedPRs: pullRequests(states: MERGED) { totalCount }
  primaryLanguage { name }
  languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
  repositoryTopics(first: 30) { nodes { topic { name } } }
  licenseInfo { spdxId }
  defaultBranchRef { name target { ... on Commit { history { totalCount } } } }
  releases { totalCount }
  latestRelease { tagName publishedAt }
  hasDiscussionsEnabled
  discussions { totalCount }
  fundingLinks { platform url }
"""
    + _README_FIELDS
    + "\n"
)

# 缓存文件名带查询字段的哈希：字段变化后旧缓存自动作废，必须整体重抓。
FIELDS_HASH = hashlib.sha256(FIELDS.encode()).hexdigest()[:8]
JOURNAL_PREFIX = "graphql_"
JOURNAL_NAME = f"{JOURNAL_PREFIX}{FIELDS_HASH}.jsonl"

QUERY_ATTEMPTS = 3


def build_query(names: list[str]) -> str:
    parts = []
    for i, full in enumerate(names):
        owner, repo = full.split("/", 1)
        parts.append(
            f"r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(repo)}) {{ {FIELDS} }}"
        )
    return "query { " + " ".join(parts) + " }"


async def fetch_batch(client: GitHubClient, names: list[str]) -> dict[str, dict | None]:
    """查询一批仓库，返回 `{仓库名: 节点}`；仓库不存在时节点为 None。

    只有 NOT_FOUND 算作"仓库不存在"；其他错误一律重试，重试用尽后把批次对半拆开再查。
    """
    query = build_query(names)
    for attempt in range(QUERY_ATTEMPTS):
        try:
            # 大批量查询常因超时返回 502/504：少量重试后就拆小批次，而不是整体放弃。
            response = await client.post(
                config.GITHUB_GRAPHQL_URL,
                json={"query": query},
                max_attempts=3,
                expect_json=True,
            )
        except GitHubError:
            log.warning("GraphQL 批次（%d 个仓库）持续失败，第 %d 次", len(names), attempt + 1)
            break
        if response.status_code == 200:
            body = response.json()
            errors = body.get("errors") or []
            if body.get("data") and all(e.get("type") == "NOT_FOUND" for e in errors):
                return {name: body["data"].get(f"r{i}") for i, name in enumerate(names)}
            log.warning("GraphQL 返回错误，重试：%s", str(errors)[:250])
            if any(e.get("type") == "RATE_LIMITED" for e in errors):
                await client.sleep(30)
        else:
            response.raise_for_status()
        await client.sleep(min(30, 3 * 2**attempt))
    if len(names) == 1:
        raise GitHubError(f"GraphQL 查询失败：{names[0]}；已缓存的进度保留，重跑即可续上")
    mid = len(names) // 2
    first, second = await asyncio.gather(
        fetch_batch(client, names[:mid]), fetch_batch(client, names[mid:])
    )
    return first | second


async def fetch_nodes(
    client: GitHubClient,
    names: list[str],
    journal: Journal,
    max_age: timedelta,
    *,
    now: datetime | None = None,
) -> dict[str, Fetched]:
    """返回 `{仓库名: Fetched(节点或 None)}`。"""
    return await collect(
        names,
        journal,
        max_age,
        lambda batch: fetch_batch(client, batch),
        label="仓库元数据",
        batch_size=config.GRAPHQL_BATCH_SIZE,
        concurrency=config.GRAPHQL_CONCURRENCY,
        now=now,
    )


def readme_path(node: dict[str, Any]) -> str | None:
    """按优先级返回第一个存在且非空的 README 文件名。"""
    for i, name in enumerate(config.README_FILENAMES):
        blob = node.get(f"readme{i}")
        if blob and blob.get("byteSize", 0) > 0:
            return name
    return None
