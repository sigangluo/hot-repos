"""Trending 每日快照：采集全部（语言，时间段）榜单，整天写成一个 Parquet 文件。

快照完整才写入：任何一页失败、或"全部语言"的某个时间段条数异常少，都不会产生当天的文件。
同一天重复运行时，当天的文件被整体替换。
"""

import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from . import config, schema, validate
from .github.client import GitHubClient
from .github.trending import TrendingError, fetch_page

log = logging.getLogger(__name__)


def snapshot_path(trending_dir: Path, day: date) -> Path:
    return trending_dir / f"{day.isoformat()}.parquet"


def snapshot_files(trending_dir: Path) -> list[Path]:
    """已有的每日快照文件，按日期升序。"""
    return sorted(trending_dir.glob("*.parquet")) if trending_dir.is_dir() else []


def read_snapshot(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist()


def write_snapshot(trending_dir: Path, day: date, rows: list[dict[str, Any]]) -> Path:
    """按 schema 写入当天的文件，先写临时文件再替换。"""
    trending_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(trending_dir, day)
    tmp = path.with_name(path.name + ".tmp")
    pq.write_table(pa.Table.from_pylist(rows, schema=schema.TRENDING), tmp, compression="zstd")
    os.replace(tmp, path)
    return path


async def collect_rows(
    client: GitHubClient,
    now: datetime,
    languages: tuple[str, ...] = tuple(config.TRENDING_LANGUAGES),
) -> list[dict[str, Any]]:
    """依次抓取"全部语言"和各语言的所有时间段，返回快照的全部行。"""
    rows: list[dict[str, Any]] = []
    for language in (config.TRENDING_ALL, *languages):
        for since in config.TRENDING_PERIODS:
            entries = await fetch_page(client, since, language)
            if language == config.TRENDING_ALL and len(entries) < config.TRENDING_MIN_ENTRIES:
                raise TrendingError(
                    f"{language}/{since} 只解析出 {len(entries)} 条（至少 {config.TRENDING_MIN_ENTRIES} 条），"
                    "页面结构可能变了，本次不写入"
                )
            if not entries:
                log.warning("%s/%s 当前没有上榜项目", language, since)
            log.info("%s/%s：%d 条", language, since, len(entries))
            rows.extend(
                {
                    "snapshot_date": now.date(),
                    "since": since,
                    "language": language,
                    "rank": rank,
                    "full_name": e.full_name,
                    "description": e.description,
                    "repo_language": e.language,
                    "stars": e.stars,
                    "forks": e.forks,
                    "period_stars": e.period_stars,
                    "built_by": list(e.built_by),
                    "captured_at": now,
                }
                for rank, e in enumerate(entries, start=1)
            )
    return rows


async def run(
    client: GitHubClient,
    trending_dir: Path,
    *,
    now: datetime | None = None,
    languages: tuple[str, ...] = tuple(config.TRENDING_LANGUAGES),
) -> Path:
    """抓取并写入今天（UTC）的快照，返回文件路径。"""
    now = now or datetime.now(UTC)
    rows = await collect_rows(client, now, languages)
    problems = validate.check_trending_rows(rows, now.date(), "本次快照")
    if problems:
        raise TrendingError("快照未通过校验，本次不写入：\n" + "\n".join(problems))
    path = write_snapshot(trending_dir, now.date(), rows)
    log.info("完成：%d 行，%d 次请求，写入 %s", len(rows), client.requests, path)
    return path
