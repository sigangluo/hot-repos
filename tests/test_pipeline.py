import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest
from conftest import classification_row, taxonomy, write_classification
from fake_github import FakeGitHub, sunday

from hot_repos import classification, config, store
from hot_repos.github.client import GitHubClient, GitHubError
from hot_repos.pipeline import DataError, Options, run
from hot_repos.validate import validate

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


async def no_sleep(_):
    pass


def run_pipeline(tmp_path, fake, now=NOW, **options):
    """以 `now` 作为"当前时间"运行一次完整采集（缓存写入的时间戳也使用它）。"""

    async def go():
        client = GitHubClient("t", rps=1e6, transport=httpx.MockTransport(fake), sleep=no_sleep)
        async with client:
            await run(
                Options(data_dir=tmp_path / "data", cache_dir=tmp_path / "cache", **options),
                client,
                now=now,
            )

    with patch("hot_repos.collect.utcnow", return_value=now):
        asyncio.run(go())


@pytest.fixture
def fake():
    return FakeGitHub({"a/one": 50000, "b/two": 30000, "c/three": 20000})


def test_full_run_writes_valid_data(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    data = tmp_path / "data"
    assert validate(data) == []
    repos = store.read_rows(data, "repos")
    assert [(r["rank"], r["full_name"], r["stars"]) for r in repos] == [
        (1, "a/one", 50000),
        (2, "b/two", 30000),
        (3, "c/three", 20000),
    ]
    assert repos[0]["contributors"] == 42
    assert repos[0]["readme_path"] == "README.md"
    assert repos[0]["homepage"] is None
    assert repos[0]["star_weeks_pages_fetched"] == 1
    assert len(store.read_rows(data, "star_weeks")) == 9
    manifest = store.read_manifest(data)
    assert manifest["snapshot_date"] == "2026-01-10"
    assert manifest["board_size"] == 3
    assert manifest["missing"] == []


def test_second_run_uses_cache_only(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    first = fake.total_calls()
    run_pipeline(tmp_path, fake, now=NOW + timedelta(hours=1), n=3)
    assert fake.total_calls() == first
    assert validate(tmp_path / "data") == []


def test_expired_cache_is_refetched(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    first = fake.total_calls()
    run_pipeline(tmp_path, fake, now=NOW + timedelta(hours=25), n=3)
    assert fake.total_calls() == 2 * first


def test_rank_history_accumulates_and_replaces_same_day(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    run_pipeline(tmp_path, fake, now=NOW + timedelta(hours=30), n=3, max_age=timedelta(0))
    run_pipeline(tmp_path, fake, now=NOW + timedelta(hours=31), n=3, max_age=timedelta(0))
    history = store.read_rows(tmp_path / "data", "rank_history")
    assert sorted({str(r["snapshot_date"]) for r in history}) == ["2026-01-10", "2026-01-11"]
    assert len(history) == 6


def test_renamed_and_missing_repositories(tmp_path):
    fake = FakeGitHub(
        {"new/name": 50000, "b/two": 30000, "gone/repo": 20000},
        renames={"old/name": "new/name"},
    )
    fake.hidden = {"gone/repo"}
    run_pipeline(tmp_path, fake, n=4)
    data = tmp_path / "data"
    manifest = store.read_manifest(data)
    repos = store.read_rows(data, "repos")
    assert manifest["aliases"] == {"new/name": ["new/name", "old/name"]}
    assert manifest["missing"] == ["gone/repo"]
    # 改名前后的两个名次合并为一个项目，取较靠前的名次；无法获取的项目在名次上留空档
    assert [(r["rank"], r["full_name"]) for r in repos] == [(1, "new/name"), (3, "b/two")]
    assert validate(data) == []


def test_skip_star_weeks_keeps_previous_history(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    before = fake.calls.get("history", 0)
    run_pipeline(
        tmp_path, fake, now=NOW + timedelta(days=2), n=3, star_weeks="skip", max_age=timedelta(0)
    )
    assert fake.calls["history"] == before
    assert len(store.read_rows(tmp_path / "data", "star_weeks")) == 9


def test_full_history_follows_all_pages(tmp_path, fake):
    fake.history_weeks = 65
    run_pipeline(tmp_path, fake, n=3, star_weeks="full")
    repos = store.read_rows(tmp_path / "data", "repos")
    assert {r["star_weeks_pages_fetched"] for r in repos} == {3}
    assert {r["star_weeks_pages_total"] for r in repos} == {3}
    assert len(store.read_rows(tmp_path / "data", "star_weeks")) == 65 * 3
    assert validate(tmp_path / "data") == []


def test_malformed_history_aborts_without_touching_data(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    before = (tmp_path / "data" / config.REPOS_FILE).read_bytes()

    def bad_history(request):
        rows = [{"week": sunday(3), "total": 7, "days": [0] * 7}]  # 逐日之和与周合计不符
        return httpx.Response(200, json=rows)

    fake.hooks["history"] = bad_history
    with pytest.raises(GitHubError, match="数据异常"):
        run_pipeline(tmp_path, fake, now=NOW + timedelta(days=3), n=3, max_age=timedelta(0))
    assert (tmp_path / "data" / config.REPOS_FILE).read_bytes() == before


def test_publish_rejects_invalid_result(tmp_path, monkeypatch, fake):
    run_pipeline(tmp_path, fake, n=3)
    before = (tmp_path / "data" / config.REPOS_FILE).read_bytes()
    monkeypatch.setattr("hot_repos.pipeline.validate", lambda _: ["boom"])
    with pytest.raises(DataError, match="boom"):
        run_pipeline(tmp_path, fake, now=NOW + timedelta(days=3), n=3, max_age=timedelta(0))
    assert (tmp_path / "data" / config.REPOS_FILE).read_bytes() == before


def test_recent_mode_warns_when_replacing_longer_history(tmp_path, fake, caplog):
    fake.history_weeks = 65
    run_pipeline(tmp_path, fake, n=3, star_weeks="full")
    with caplog.at_level("WARNING"):
        run_pipeline(tmp_path, fake, now=NOW + timedelta(days=2), n=3, max_age=timedelta(0))
    assert "更长的周 Star 历史" in caplog.text


def test_pipeline_carries_classification_over(tmp_path, fake):
    run_pipeline(tmp_path, fake, n=3)
    data = tmp_path / "data"
    names = [r["full_name"] for r in store.read_rows(data, "repos")]
    write_classification(data, [classification_row(names[0]), classification_row("gone/repo")])
    assert validate(data) != []  # gone/repo 不在总榜
    run_pipeline(tmp_path, fake, n=3)
    assert validate(data) == []
    assert [r["full_name"] for r in classification.read_rows(data)] == [names[0]]
    assert classification.read_taxonomy(data) == taxonomy()
