"""采集流程：总榜 → 元数据 → 贡献者数 → 周 Star 分布 → 校验 → 发布到 data/。"""

import logging
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from . import classification, config, schema, store
from .cache import Journal, utcnow
from .github import graphql
from .github.client import GitHubClient
from .github.contributors import fetch_counts
from .github.graphql import fetch_nodes
from .github.search import top_by_stars
from .github.star_weeks import StarWeeks, fetch_star_weeks
from .transform import canonical_groups, repo_row
from .validate import validate

log = logging.getLogger(__name__)

StarWeeksMode = Literal["recent", "full", "skip"]


class DataError(RuntimeError):
    """采集结果未通过校验。data/ 保持原样，未被修改。"""


@dataclass(frozen=True)
class Options:
    n: int
    data_dir: Path = config.DATA_DIR
    cache_dir: Path = config.CACHE_DIR
    max_age: timedelta = timedelta(hours=config.DEFAULT_MAX_AGE_HOURS)
    star_weeks: StarWeeksMode = (
        "recent"  # recent: 最近一页；full: 全部页；skip: 沿用 data/ 中已有的
    )


async def run(opts: Options, client: GitHubClient, *, now: datetime | None = None) -> None:
    now = now or utcnow()
    cache_dir = opts.cache_dir

    log.info("1/4 总榜")
    board = await top_by_stars(client, opts.n, cache_dir, opts.max_age, now)
    rank_of = {name.lower(): i for i, (name, _) in enumerate(board.items, 1)}
    stars_of = {name.lower(): stars for name, stars in board.items}
    names = sorted(name for name, _ in board.items)

    log.info("2/4 仓库元数据")
    fetched = await fetch_nodes(
        client, names, Journal(cache_dir / graphql.JOURNAL_NAME), opts.max_age, now=now
    )
    nodes = {n: f.value for n, f in fetched.items() if f.value is not None}
    missing = sorted(n for n, f in fetched.items() if f.value is None)
    groups = canonical_groups(nodes, {n: fetched[n].fetched_at for n in nodes})
    current = sorted(g.node["nameWithOwner"] for g in groups)

    log.info("3/4 贡献者数")
    contributors = await fetch_counts(
        client, current, Journal(cache_dir / "contributors.jsonl"), opts.max_age, now=now
    )

    log.info("4/4 周 Star 分布（%s）", opts.star_weeks)
    star_weeks = await _star_weeks(opts, client, current, now)

    snapshot = now.date()
    repos, weeks, ranks = [], [], []
    for g in sorted(groups, key=lambda g: g.node["nameWithOwner"]):
        name = g.node["nameWithOwner"]
        source = min(g.query_names, key=lambda a: rank_of[a.lower()])
        row = repo_row(g.node, contributors[name].value)
        history = star_weeks.get(name)
        row |= {
            "rank": rank_of[source.lower()],
            "fetched_at": g.fetched_at,
            "star_weeks_fetched_at": history.fetched_at if history else None,
            "star_weeks_pages_fetched": history.pages_fetched if history else None,
            "star_weeks_pages_total": history.pages_total if history else None,
        }
        repos.append(row)
        ranks.append(
            {
                "snapshot_date": snapshot,
                "rank": row["rank"],
                "full_name": name,
                "stars": stars_of[source.lower()],
                "captured_at": board.captured_at,
            }
        )
        if history:
            weeks += [{"full_name": name, **w} for w in history.weeks]
    repos.sort(key=lambda r: r["rank"])
    weeks.sort(key=lambda w: (w["full_name"], w["week_start"]))
    manifest = {
        "schema_version": config.SCHEMA_VERSION,
        "snapshot_date": snapshot.isoformat(),
        "board_size": opts.n,
        "rank_captured_at": board.captured_at.isoformat(),
        "run_at": now.isoformat(),
        "star_weeks_per_page": config.STAR_WEEKS_PER_PAGE,
        "aliases": {
            g.node["nameWithOwner"]: g.query_names for g in groups if len(g.query_names) > 1
        },
        "missing": missing,
    }
    ranks = store.merge_rank_history(
        store.read_rows(opts.data_dir, "rank_history"), ranks, snapshot
    )

    _publish(opts, {"repos": repos, "star_weeks": weeks, "rank_history": ranks}, manifest)
    _compact_caches(cache_dir, now)
    log.info(
        "完成：%d 个项目，%d 条周分布，%d 个无法获取；共 %d 次请求",
        len(repos),
        len(weeks),
        len(missing),
        client.requests,
    )


async def _star_weeks(
    opts: Options, client: GitHubClient, names: list[str], now: datetime
) -> dict[str, StarWeeks]:
    if opts.star_weeks == "skip":
        return _previous_star_weeks(opts.data_dir, set(names))
    if opts.star_weeks == "recent":
        longer = sum(
            (r["star_weeks_pages_fetched"] or 0) > 1
            for r in store.read_rows(opts.data_dir, "repos")
        )
        if longer:
            log.warning(
                "data/ 中有 %d 个项目已有更长的周 Star 历史，本次只取最近一页，会被替换为近期数据；"
                "要保留请使用 --star-weeks full 或 skip",
                longer,
            )
    results = await fetch_star_weeks(
        client,
        names,
        Journal(opts.cache_dir / "star_weeks.jsonl"),
        opts.max_age,
        full=opts.star_weeks == "full",
        now=now,
    )
    return {n: r for n, r in results.items() if r is not None}


def _previous_star_weeks(data_dir: Path, names: set[str]) -> dict[str, StarWeeks]:
    """沿用 data/ 中已有的周分布。"""
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for w in store.read_rows(data_dir, "star_weeks"):
        by_repo[w["full_name"]].append({k: w[k] for k in ("week_start", "stars", "days")})
    return {
        r["full_name"]: StarWeeks(
            by_repo[r["full_name"]],
            r["star_weeks_pages_fetched"],
            r["star_weeks_pages_total"],
            r["star_weeks_fetched_at"],
        )
        for r in store.read_rows(data_dir, "repos")
        if r["full_name"] in names and r["star_weeks_fetched_at"] is not None
    }


def _publish(opts: Options, tables: dict[str, list[dict]], manifest: dict) -> None:
    """先写入暂存目录并校验，通过后才替换 data/，避免留下半成品。"""
    staging = opts.cache_dir / "staging"
    shutil.rmtree(staging, ignore_errors=True)
    for name in schema.TABLES:
        store.write_rows(staging, name, tables[name])
    store.write_manifest(staging, manifest)
    _carry_classification(opts.data_dir, staging, tables["repos"], manifest["aliases"])
    problems = validate(staging)
    if problems:
        raise DataError("采集结果未通过校验，data/ 未修改：\n" + "\n".join(problems[:20]))
    store.publish(staging, opts.data_dir)
    shutil.rmtree(staging, ignore_errors=True)


def _carry_classification(
    data_dir: Path, staging: Path, repos: list[dict], aliases: dict[str, list[str]]
) -> None:
    """项目分类沿用到暂存目录：改名的项目换成当前名称，已不在总榜里的项目其分类结果被丢弃。"""
    taxonomy = classification.read_taxonomy(data_dir)
    if taxonomy is None:
        return
    classification.write_taxonomy(staging, taxonomy)
    if not (data_dir / config.CLASSIFICATION_FILE).exists():  # 只有目录、还没有分类结果
        return
    rows, renamed, dropped = classification.reconcile(
        classification.read_rows(data_dir), [r["full_name"] for r in repos], aliases
    )
    if renamed or dropped:
        log.info("项目分类：%d 个项目改名，%d 个项目已不在总榜而被丢弃", renamed, len(dropped))
        if dropped:
            log.info("被丢弃的项目：%s", "、".join(dropped))
    classification.write_rows(staging, rows)


def _compact_caches(cache_dir: Path, now: datetime) -> None:
    """合并日志中被覆盖的旧记录，并删除查询字段已变化的过期缓存。"""
    for path in cache_dir.glob(f"{graphql.JOURNAL_PREFIX}*.jsonl"):
        if path.name != graphql.JOURNAL_NAME:
            path.unlink()
    for path in cache_dir.glob("*.jsonl"):
        Journal(path).compact(retention=timedelta(days=config.CACHE_RETENTION_DAYS), now=now)
