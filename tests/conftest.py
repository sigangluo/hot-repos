"""测试夹具：生成一份最小的合法数据集。"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from hot_repos import config, schema

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


def repo_row(name: str, rank: int, stars: int) -> dict:
    return {
        "full_name": name,
        "rank": rank,
        "description": None,
        "homepage": None,
        "owner_type": "Organization",
        "created_at": datetime(2020, 1, 1, tzinfo=UTC),
        "pushed_at": NOW,
        "updated_at": NOW,
        "is_archived": False,
        "is_fork": False,
        "is_template": False,
        "disk_usage_kb": 10,
        "stars": stars,
        "forks": 1,
        "watchers": 1,
        "open_issues": 0,
        "closed_issues": 0,
        "open_prs": 0,
        "merged_prs": 0,
        "discussions_enabled": False,
        "discussions": 0,
        "primary_language": "Python",
        "languages": [{"name": "Python", "bytes": 100}],
        "topics": ["a", "b"],
        "license": "MIT",
        "default_branch": "main",
        "commit_count": 5,
        "contributors": 2,
        "release_count": 1,
        "latest_release_tag": "v1",
        "latest_release_at": NOW,
        "funding": [],
        "readme_path": "README.md",
        "fetched_at": NOW,
        "star_weeks_fetched_at": NOW,
        "star_weeks_pages_fetched": 1,
        "star_weeks_pages_total": 2,
    }


def default_manifest(**changes) -> dict:
    return {
        "schema_version": config.SCHEMA_VERSION,
        "snapshot_date": "2026-01-10",
        "board_size": 3,
        "rank_captured_at": NOW.isoformat(),
        "run_at": NOW.isoformat(),
        "star_weeks_per_page": 30,
        "aliases": {},
        "missing": ["gone/repo"],
    } | changes


def write_dataset(path: Path, repos=None, weeks=None, ranks=None, manifest=None) -> Path:
    repos = repos or [repo_row("a/one", 1, 200), repo_row("b/two", 3, 100)]
    weeks = weeks or [
        {"full_name": "a/one", "week_start": date(2026, 1, 4), "stars": 7, "days": [1] * 7},
        {"full_name": "a/one", "week_start": date(2026, 1, 11), "stars": 0, "days": [0] * 7},
    ]
    ranks = ranks or [
        {
            "snapshot_date": date(2026, 1, 10),
            "rank": r["rank"],
            "full_name": r["full_name"],
            "stars": r["stars"],
            "captured_at": NOW,
        }
        for r in repos
    ]
    manifest = manifest or default_manifest()
    path.mkdir(parents=True, exist_ok=True)
    for name, rows, file in [
        ("repos", repos, config.REPOS_FILE),
        ("star_weeks", weeks, config.STAR_WEEKS_FILE),
        ("rank_history", ranks, config.RANK_HISTORY_FILE),
    ]:
        pq.write_table(pa.Table.from_pylist(rows, schema=schema.TABLES[name]), path / file)
    (path / config.MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    return path


def snapshot_rows(**changes) -> list[dict]:
    rows = []
    for since in config.TRENDING_PERIODS:
        for rank in (1, 2):
            rows.append(
                {
                    "snapshot_date": date(2026, 1, 10),
                    "since": since,
                    "language": "all",
                    "rank": rank,
                    "full_name": f"o{rank}/r",
                    "description": None,
                    "repo_language": None,
                    "stars": 10,
                    "forks": 1,
                    "period_stars": 3,
                    "built_by": [],
                    "captured_at": NOW,
                }
            )
    return [r | changes for r in rows]


def write_trending(directory: Path, rows: list[dict], name: str = "2026-01-10.parquet") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema.TRENDING), directory / name)


def taxonomy() -> dict:
    return {
        "note": "测试说明",
        "forms": {"app": "应用", "list": "资源清单"},
        "nodes": [
            {"id": "dev", "label": "开发"},
            {"id": "dev.tools", "label": "工具", "parent": "dev"},
            {"id": "dev.tools.cli", "label": "命令行", "parent": "dev.tools"},
            {"id": "ai", "label": "人工智能"},
        ],
    }


def classification_row(name: str, **changes) -> dict:
    return {
        "full_name": name,
        "category": "dev.tools.cli",
        "related": ["ai"],
        "forms": ["app"],
        "summary": "一个工具",
        "review_reason": None,
    } | changes


def write_classification(
    path: Path, rows: list[dict] | None = None, tax: dict | None = None
) -> None:
    """在 path 下写入分类目录与结果（默认给 a/one 一行）。"""
    from hot_repos import classification

    classification.write_taxonomy(path, tax or taxonomy())
    classification.write_rows(path, rows if rows is not None else [classification_row("a/one")])


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    return write_dataset(tmp_path / "data")
