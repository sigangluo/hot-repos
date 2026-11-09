"""数据完整性与一致性检查。只读，返回问题列表，空列表表示通过。"""

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import config, schema


def validate(data_dir: Path = config.DATA_DIR) -> list[str]:
    """检查 data_dir 下的全部文件，返回问题描述列表。"""
    problems: list[str] = []
    tables = _load_tables(data_dir, problems)
    manifest = _load_manifest(data_dir, problems)
    if "repos" in tables:
        _check_repos(tables["repos"].to_pylist(), problems)
    if "rank_history" in tables:
        _check_rank_history(tables["rank_history"].to_pylist(), problems)
    if "star_weeks" in tables:
        _check_star_weeks(tables["star_weeks"].to_pylist(), problems)
    if len(tables) == len(schema.TABLES):
        repos = tables["repos"].to_pylist()
        _check_cross_table(
            repos,
            tables["rank_history"].to_pylist(),
            tables["star_weeks"].to_pylist(),
            manifest,
            problems,
        )
    problems += validate_trending(data_dir / config.TRENDING_DIR_NAME)
    return problems


_SNAPSHOT_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})\.parquet")


def validate_trending(trending_dir: Path) -> list[str]:
    """检查 Trending 的每日快照。目录不存在表示尚未开始采集，不算问题。"""
    problems: list[str] = []
    for path in sorted(trending_dir.glob("*.parquet")):
        label = f"{config.TRENDING_DIR_NAME}/{path.name}"
        match = _SNAPSHOT_NAME.fullmatch(path.name)
        try:
            day = date.fromisoformat(match[1]) if match else None
        except ValueError:
            day = None
        if day is None:
            problems.append(f"{label}: 文件名应为 YYYY-MM-DD.parquet")
            continue
        table = pq.read_table(path)
        if not table.schema.equals(schema.TRENDING, check_metadata=False):
            problems.append(
                f"{label}: 表结构与 schema.py 不一致\n  实际: {table.schema}\n  期望: {schema.TRENDING}"
            )
            continue
        problems += check_trending_rows(table.to_pylist(), day, label)
    return problems


def check_trending_rows(rows: list[dict], day: date, label: str) -> list[str]:
    """检查某一天的快照行，返回问题列表。写入前和校验已有文件时共用。"""
    problems: list[str] = []
    if not rows:
        return [f"{label}: 没有任何数据"]
    if {r["snapshot_date"] for r in rows} != {day}:
        problems.append(f"{label}: snapshot_date 与文件名不一致")
    captured = {r["captured_at"] for r in rows}
    if len(captured) > 1:
        problems.append(f"{label}: 同一快照的 captured_at 不一致")
    elif next(iter(captured)).astimezone(UTC).date() != day:
        problems.append(f"{label}: captured_at 的日期（UTC）与文件名不一致")

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["since"], r["language"]), []).append(r)
    for since in config.TRENDING_PERIODS:
        if (since, config.TRENDING_ALL) not in groups:
            problems.append(f"{label}: 缺少「全部语言」的 {since} 榜单")
    for (since, language), group in groups.items():
        key = f"{label} {language}/{since}"
        if since not in config.TRENDING_PERIODS:
            problems.append(f"{key}: 未知的时间段")
        ranks = [r["rank"] for r in group]
        if sorted(ranks) != list(range(1, len(group) + 1)):
            problems.append(f"{key}: rank 应从 1 开始连续且不重复")
        for d in _duplicates(r["full_name"].lower() for r in group):
            problems.append(f"{key}: full_name 重复: {d}")
        for r in group:
            if r["full_name"].count("/") != 1:
                problems.append(f"{key}: full_name 格式应为 owner/repo: {r['full_name']}")
            for c in ("stars", "forks", "period_stars"):
                if r[c] < 0:
                    problems.append(f"{key}: {r['full_name']} {c} 为负数")
    return problems


def _load_tables(data_dir: Path, problems: list[str]) -> dict[str, pa.Table]:
    tables = {}
    for name, filename in config.TABLE_FILES.items():
        path = data_dir / filename
        if not path.exists():
            problems.append(f"{filename}: 文件不存在")
            continue
        table = pq.read_table(path)
        expected = schema.TABLES[name]
        if not table.schema.equals(expected, check_metadata=False):
            problems.append(
                f"{filename}: 表结构与 schema.py 不一致\n  实际: {table.schema}\n  期望: {expected}"
            )
            continue
        tables[name] = table
    return tables


def _load_manifest(data_dir: Path, problems: list[str]) -> dict | None:
    path = data_dir / config.MANIFEST_FILE
    if not path.exists():
        problems.append(f"{config.MANIFEST_FILE}: 文件不存在")
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    ok = True
    for key, type_ in schema.MANIFEST_FIELDS.items():
        if key not in manifest:
            problems.append(f"{config.MANIFEST_FILE}: 缺少字段 {key}")
            ok = False
        elif not isinstance(manifest[key], type_) or isinstance(manifest[key], bool):
            problems.append(f"{config.MANIFEST_FILE}: 字段 {key} 应为 {type_.__name__}")
            ok = False
    for key in manifest.keys() - schema.MANIFEST_FIELDS.keys():
        problems.append(f"{config.MANIFEST_FILE}: 未定义的字段 {key}")
        ok = False
    if ok and manifest["schema_version"] != config.SCHEMA_VERSION:
        problems.append(
            f"{config.MANIFEST_FILE}: schema_version 为 {manifest['schema_version']}，"
            f"代码期望 {config.SCHEMA_VERSION}"
        )
        ok = False
    return manifest if ok else None


def _duplicates(values) -> list:
    seen, dup = set(), []
    for v in values:
        if v in seen:
            dup.append(v)
        seen.add(v)
    return dup


def _check_repos(rows: list[dict], problems: list[str]) -> None:
    f = config.REPOS_FILE
    for d in _duplicates(r["full_name"].lower() for r in rows):
        problems.append(f"{f}: full_name 重复（忽略大小写）: {d}")
    for d in _duplicates(r["rank"] for r in rows):
        problems.append(f"{f}: rank 重复: {d}")
    counts = [
        "disk_usage_kb",
        "stars",
        "forks",
        "watchers",
        "open_issues",
        "closed_issues",
        "open_prs",
        "merged_prs",
        "discussions",
        "release_count",
        "commit_count",
        "contributors",
    ]
    for r in rows:
        name = r["full_name"]
        if r["full_name"].count("/") != 1:
            problems.append(f"{f}: full_name 格式应为 owner/repo: {name}")
        if r["rank"] < 1:
            problems.append(f"{f}: {name} rank 应从 1 开始")
        for c in counts:
            if r[c] is not None and r[c] < 0:
                problems.append(f"{f}: {name} {c} 为负数")
        if r["updated_at"] < r["created_at"]:
            problems.append(f"{f}: {name} updated_at 早于 created_at")
        if len(set(r["topics"])) != len(r["topics"]):
            problems.append(f"{f}: {name} topics 含重复项")
        if r["readme_path"] is not None and r["readme_path"] not in config.README_FILENAMES:
            problems.append(f"{f}: {name} readme_path 不在已知文件名中: {r['readme_path']}")
        if (r["latest_release_tag"] is None) != (r["latest_release_at"] is None):
            problems.append(
                f"{f}: {name} latest_release_tag 与 latest_release_at 应同时有值或同时为空"
            )
        if r["discussions"] > 0 and not r["discussions_enabled"]:
            problems.append(f"{f}: {name} 未启用讨论区但 discussions 大于 0")
        _check_star_weeks_coverage(r, problems)


def _check_star_weeks_coverage(r: dict, problems: list[str]) -> None:
    f = config.REPOS_FILE
    group = [r["star_weeks_fetched_at"], r["star_weeks_pages_fetched"], r["star_weeks_pages_total"]]
    if any(v is None for v in group) and any(v is not None for v in group):
        problems.append(f"{f}: {r['full_name']} star_weeks_* 三列应同时有值或同时为空")
    elif r["star_weeks_pages_fetched"] is not None:
        fetched, total = r["star_weeks_pages_fetched"], r["star_weeks_pages_total"]
        if not 1 <= fetched <= total:
            problems.append(
                f"{f}: {r['full_name']} star_weeks_pages_fetched 应在 1 到 pages_total 之间"
            )


def _check_rank_history(rows: list[dict], problems: list[str]) -> None:
    f = config.RANK_HISTORY_FILE
    by_date: dict[date, list[dict]] = {}
    for r in rows:
        by_date.setdefault(r["snapshot_date"], []).append(r)
    for day, group in by_date.items():
        for d in _duplicates(r["rank"] for r in group):
            problems.append(f"{f}: {day} rank 重复: {d}")
        for d in _duplicates(r["full_name"].lower() for r in group):
            problems.append(f"{f}: {day} full_name 重复: {d}")
        if len({r["captured_at"] for r in group}) > 1:
            problems.append(f"{f}: {day} 同一快照的 captured_at 不一致")
        ordered = sorted(group, key=lambda r: r["rank"])
        if any(a["stars"] < b["stars"] for a, b in zip(ordered, ordered[1:], strict=False)):
            problems.append(f"{f}: {day} 名次与 stars 不是降序对应")


def _check_star_weeks(rows: list[dict], problems: list[str]) -> None:
    f = config.STAR_WEEKS_FILE
    for name, week in _duplicates((r["full_name"], r["week_start"]) for r in rows):
        problems.append(f"{f}: ({name}, {week}) 重复")
    by_repo: dict[str, list[date]] = {}
    for r in rows:
        by_repo.setdefault(r["full_name"], []).append(r["week_start"])
    for name, starts in by_repo.items():
        starts.sort()
        if any(b - a != timedelta(days=7) for a, b in zip(starts, starts[1:], strict=False)):
            problems.append(f"{f}: {name} 的周不连续")
    for r in rows:
        key = f"({r['full_name']}, {r['week_start']})"
        if r["week_start"].weekday() != 6:
            problems.append(f"{f}: {key} week_start 不是周日")
        if len(r["days"]) != 7 or any(d < 0 for d in r["days"]):
            problems.append(f"{f}: {key} days 应为 7 个非负整数")
        elif sum(r["days"]) != r["stars"]:
            problems.append(f"{f}: {key} days 之和与 stars 不一致")
        if r["stars"] < 0:
            problems.append(f"{f}: {key} stars 为负数")


def _check_cross_table(
    repos: list[dict],
    ranks: list[dict],
    weeks: list[dict],
    manifest: dict | None,
    problems: list[str],
) -> None:
    names = {r["full_name"] for r in repos}
    lower = {n.lower() for n in names}

    unknown = {r["full_name"] for r in weeks} - names
    for n in sorted(unknown):
        problems.append(f"{config.STAR_WEEKS_FILE}: {n} 不在 {config.REPOS_FILE} 中")
    unknown = {r["full_name"] for r in ranks if r["snapshot_date"] == _latest(ranks)} - names
    for n in sorted(unknown):
        problems.append(f"{config.RANK_HISTORY_FILE}: 最新快照中的 {n} 不在 {config.REPOS_FILE} 中")

    by_repo = {r["full_name"]: r for r in repos}
    counts: dict[str, int] = {}
    for w in weeks:
        counts[w["full_name"]] = counts.get(w["full_name"], 0) + 1
    for name, n in counts.items():
        repo = by_repo.get(name)
        if repo is None:
            continue
        if repo["star_weeks_pages_fetched"] is None:
            problems.append(f"{config.REPOS_FILE}: {name} 有周分布数据但 star_weeks_* 为空")
        elif manifest and n > repo["star_weeks_pages_fetched"] * manifest["star_weeks_per_page"]:
            problems.append(f"{config.STAR_WEEKS_FILE}: {name} 周数超过已抓页数能容纳的上限")

    if manifest is None:
        return
    snapshot = date.fromisoformat(manifest["snapshot_date"])
    if _latest(ranks) != snapshot:
        problems.append(
            f"{config.MANIFEST_FILE}: snapshot_date {snapshot} 不是 {config.RANK_HISTORY_FILE} 的最新快照"
        )
    current = {r["rank"]: r["full_name"] for r in ranks if r["snapshot_date"] == snapshot}
    in_repos = {r["rank"]: r["full_name"] for r in repos}
    if current != in_repos:
        diff = sorted(
            current.keys() ^ in_repos.keys()
            | {k for k in current.keys() & in_repos.keys() if current[k] != in_repos[k]}
        )
        problems.append(
            f"{config.REPOS_FILE} 与 {config.RANK_HISTORY_FILE} 最新快照的名次不一致，"
            f"涉及名次: {diff[:10]}{'…' if len(diff) > 10 else ''}"
        )

    if len(repos) > manifest["board_size"]:
        problems.append(f"{config.MANIFEST_FILE}: board_size 小于 {config.REPOS_FILE} 行数")
    for cur, group in manifest["aliases"].items():
        if cur not in names:
            problems.append(
                f"{config.MANIFEST_FILE}: aliases 的键 {cur} 不在 {config.REPOS_FILE} 中"
            )
        if cur not in group:
            problems.append(f"{config.MANIFEST_FILE}: aliases[{cur}] 应包含当前名称")
    for m in manifest["missing"]:
        if m.lower() in lower:
            problems.append(
                f"{config.MANIFEST_FILE}: missing 中的 {m} 同时出现在 {config.REPOS_FILE}"
            )
    for key in ("rank_captured_at", "run_at"):
        try:
            if datetime.fromisoformat(manifest[key]).tzinfo is None:
                problems.append(f"{config.MANIFEST_FILE}: {key} 缺少时区")
        except ValueError:
            problems.append(f"{config.MANIFEST_FILE}: {key} 不是有效的 ISO 8601 时间")


def _latest(ranks: list[dict]) -> date | None:
    return max((r["snapshot_date"] for r in ranks), default=None)
