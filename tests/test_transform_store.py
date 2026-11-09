from datetime import UTC, date, datetime

import pytest
from fake_github import make_node

from hot_repos import schema, store
from hot_repos.transform import canonical_groups, repo_row

T = datetime(2026, 1, 1, tzinfo=UTC)


def test_repo_row_maps_every_repos_column_except_pipeline_ones():
    row = repo_row(make_node("o/r", 10), contributors=5)
    pipeline_columns = {
        "rank", "fetched_at", "star_weeks_fetched_at", "star_weeks_pages_fetched",
        "star_weeks_pages_total",
    }  # fmt: skip
    assert set(row) == set(schema.REPOS.names) - pipeline_columns
    assert row["homepage"] is None  # 空字符串统一为 None
    assert row["languages"] == [{"name": "Python", "bytes": 900}]
    assert row["topics"] == ["ai"]
    assert row["contributors"] == 5
    assert row["created_at"].tzinfo is not None


def test_repo_row_handles_empty_repository():
    node = make_node(
        "o/r", 0, defaultBranchRef=None, latestRelease=None, licenseInfo=None,
        primaryLanguage=None, pushedAt=None, diskUsage=None, description=None,
        languages={"edges": []},
    )  # fmt: skip
    row = repo_row(node, contributors=None)
    assert row["default_branch"] is None
    assert row["commit_count"] is None
    assert row["latest_release_tag"] is None
    assert row["license"] is None
    assert row["languages"] == []
    assert row["disk_usage_kb"] is None


def test_renamed_repo_merges_aliases_and_keeps_freshest_metadata():
    old = make_node("new/repo", 100)
    current = make_node("new/repo", 120)
    groups = canonical_groups(
        {"old/repo": old, "new/repo": current},
        {"old/repo": T, "new/repo": T.replace(hour=2)},
    )
    assert len(groups) == 1
    assert groups[0].node is current
    assert groups[0].query_names == ["new/repo", "old/repo"]
    assert groups[0].fetched_at == T.replace(hour=2)


def test_rank_history_merge_replaces_same_day_and_sorts():
    def row(day, rank):
        return {
            "snapshot_date": day,
            "rank": rank,
            "full_name": f"o/{rank}",
            "stars": 1,
            "captured_at": T,
        }

    existing = [row(date(2026, 1, 1), 1), row(date(2026, 1, 2), 1), row(date(2026, 1, 2), 2)]
    merged = store.merge_rank_history(existing, [row(date(2026, 1, 2), 7)], date(2026, 1, 2))
    assert [(r["snapshot_date"].day, r["rank"]) for r in merged] == [(1, 1), (2, 7)]


def test_write_rows_enforces_schema(tmp_path):
    import pyarrow as pa
    import pytest

    with pytest.raises((pa.ArrowInvalid, KeyError, ValueError, TypeError)):
        store.write_rows(
            tmp_path, "rank_history", [{"snapshot_date": date(2026, 1, 1), "rank": None}]
        )
    assert not (tmp_path / "rank_history.parquet").exists()


def test_publish_replaces_all_files(tmp_path, dataset):
    from hot_repos import config

    target = tmp_path / "target"
    target.mkdir()
    (target / config.REPOS_FILE).write_bytes(b"old")
    store.publish(dataset, target)
    assert (target / config.REPOS_FILE).read_bytes() == (dataset / config.REPOS_FILE).read_bytes()
    assert sorted(p.name for p in target.iterdir()) == sorted(p.name for p in dataset.iterdir())


def test_publish_leaves_target_untouched_when_copy_fails(tmp_path, dataset, monkeypatch):
    import shutil

    from hot_repos import config

    target = tmp_path / "target"
    target.mkdir()
    (target / config.REPOS_FILE).write_bytes(b"old")
    real_copy, calls = shutil.copyfile, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 3:
            raise OSError("disk full")
        return real_copy(src, dst)

    monkeypatch.setattr(shutil, "copyfile", flaky)
    with pytest.raises(OSError, match="disk full"):
        store.publish(dataset, target)
    assert [p.name for p in target.iterdir()] == [config.REPOS_FILE]
    assert (target / config.REPOS_FILE).read_bytes() == b"old"
