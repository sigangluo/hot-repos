"""各类数据源：总榜搜索、GraphQL、贡献者数、周 Star 分布。"""

import asyncio
from datetime import timedelta

import httpx
import pytest
from fake_github import FakeGitHub, make_node, sunday

from hot_repos import config
from hot_repos.cache import Journal, utcnow
from hot_repos.github import graphql
from hot_repos.github.client import GitHubClient, GitHubError
from hot_repos.github.contributors import count_contributors
from hot_repos.github.search import top_by_stars
from hot_repos.github.star_weeks import fetch_page, fetch_star_weeks, last_page, validate_page

DAY = timedelta(hours=24)


async def no_sleep(_):
    pass


def make_client(handler):
    return GitHubClient("t", rps=1e6, transport=httpx.MockTransport(handler), sleep=no_sleep)


def run(handler, coro_fn):
    async def go():
        async with make_client(handler) as client:
            return await coro_fn(client)

    return asyncio.run(go())


# ---------- 总榜搜索 ----------


def test_search_crosses_1000_without_losing_boundary_ties(tmp_path):
    repos = {f"o/r{i:04}": 20000 - i // 3 for i in range(1400)}  # 每 3 个项目同 Star 数
    fake = FakeGitHub(repos)
    board = run(fake, lambda c: top_by_stars(c, 1200, tmp_path, DAY))
    expected = sorted(repos.values(), reverse=True)[:1200]
    assert len(board.items) == 1200
    assert len({name for name, _ in board.items}) == 1200
    assert [stars for _, stars in board.items] == expected
    assert fake.calls["search"] > 12  # 超过单个区间的容量，必须分段

    calls = fake.calls["search"]
    again = run(fake, lambda c: top_by_stars(c, 1200, tmp_path, DAY))
    assert again.items == board.items
    assert fake.calls["search"] == calls  # 命中缓存


def test_search_resumes_from_progress(tmp_path):
    repos = {f"o/r{i:04}": 20000 - i // 3 for i in range(1400)}
    fake = FakeGitHub(repos)
    original = fake.search
    state = {"n": 0}

    def flaky(request):
        state["n"] += 1
        if state["n"] >= 11:  # 第一个区间读完、写入进度之后，网络持续不可用
            raise httpx.ConnectError("down")
        return original(request)

    fake.search = flaky
    with pytest.raises(GitHubError):
        run(fake, lambda c: top_by_stars(c, 1200, tmp_path, DAY))
    assert (tmp_path / "search_1200_progress.json").exists()
    board = run(FakeGitHub(repos), lambda c: top_by_stars(c, 1200, tmp_path, DAY))
    assert len(board.items) == 1200
    assert not (tmp_path / "search_1200_progress.json").exists()


def test_search_stale_cache_is_ignored(tmp_path):
    fake = FakeGitHub({"a/one": 50000, "b/two": 30000})
    run(fake, lambda c: top_by_stars(c, 2, tmp_path, DAY))
    calls = fake.calls["search"]
    run(fake, lambda c: top_by_stars(c, 2, tmp_path, DAY, now=utcnow() + timedelta(days=2)))
    assert fake.calls["search"] == calls + 1


# ---------- GraphQL ----------


def test_graphql_not_found_is_missing_but_other_errors_are_retried():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(
                200, json={"data": {"r0": None}, "errors": [{"type": "INTERNAL", "path": ["r0"]}]}
            )
        return httpx.Response(200, json={"data": {"r0": make_node("o/r", 1)}})

    nodes = run(handler, lambda c: graphql.fetch_batch(c, ["o/r"]))
    assert nodes["o/r"]["nameWithOwner"] == "o/r"
    assert len(calls) == 2


def test_graphql_not_found_maps_to_none():
    fake = FakeGitHub({"a/one": 1})
    fake.hidden = {"b/two"}
    fake.repos["b/two"] = 2
    nodes = run(fake, lambda c: graphql.fetch_batch(c, ["a/one", "b/two"]))
    assert nodes["a/one"] is not None
    assert nodes["b/two"] is None


def test_graphql_splits_failing_batch_down_to_the_bad_repository():
    fake = FakeGitHub({"a/one": 1, "b/two": 2, "c/three": 3, "d/four": 4})
    original = fake.graphql

    def poison(request):
        # 含 d/four 的查询持续返回内部错误；单独查询其他仓库正常
        if b'"d/four"' in request.content or b'name: \\"four\\"' in request.content:
            return httpx.Response(200, json={"data": None, "errors": [{"type": "INTERNAL"}]})
        return original(request)

    fake.graphql = poison
    with pytest.raises(GitHubError, match="d/four"):
        run(fake, lambda c: graphql.fetch_batch(c, ["a/one", "b/two", "c/three", "d/four"]))


def test_readme_path_prefers_first_nonempty_name():
    node = make_node("o/r", 1, readme0=None, readme1={"byteSize": 5}, readme2={"byteSize": 9})
    assert graphql.readme_path(node) == config.README_FILENAMES[1]
    assert graphql.readme_path(make_node("o/r", 1, readme0={"byteSize": 0})) is None


def test_query_does_not_download_readme_text():
    assert "text" not in graphql.FIELDS.replace("fetched", "")
    assert "byteSize" in graphql.FIELDS


# ---------- 贡献者数 ----------


def test_contributors_uses_last_page_not_next_page():
    fake = FakeGitHub({"o/r": 1})
    assert run(fake, lambda c: count_contributors(c, "o/r")) == 42


def test_contributors_without_link_counts_body():
    handler = lambda r: httpx.Response(200, json=[{"login": "x"}])  # noqa: E731
    assert run(handler, lambda c: count_contributors(c, "o/r")) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(204),
        httpx.Response(404),
        httpx.Response(403, json={"message": "The history or contributor list is too large"}),
    ],
)
def test_contributors_unavailable_is_none(response):
    assert run(lambda r: response, lambda c: count_contributors(c, "o/r")) is None


# ---------- 周 Star 分布 ----------


def week(ts, total=7, days=None):
    return {"week": ts, "total": total, "days": days or [total, 0, 0, 0, 0, 0, 0]}


def test_validate_page_rejects_inconsistent_daily_totals():
    with pytest.raises(ValueError, match="之和"):
        validate_page([week(sunday(1), 5, [4, 0, 0, 0, 0, 0, 0])])


def test_validate_page_rejects_duplicates_and_wrong_order():
    with pytest.raises(ValueError, match="唯一"):
        validate_page([week(sunday(1)), week(sunday(1))])
    with pytest.raises(ValueError, match="从新到旧"):
        validate_page([week(sunday(1)), week(sunday(2))])


def test_validate_page_rejects_non_sunday_week():
    with pytest.raises(ValueError, match="周日"):
        validate_page([week(sunday(1) + 86400)])


def test_validate_page_rejects_oversized_page():
    rows = [week(sunday(100 - i)) for i in range(31)]
    with pytest.raises(ValueError, match="最多"):
        validate_page(rows)


def test_last_page():
    assert last_page(None) == 1
    assert last_page('<https://x?page=9>; rel="last"') == 9
    with pytest.raises(ValueError):
        last_page('<https://x?page=2>; rel="next"')


def test_fetch_page_returns_none_for_missing_repo():
    assert run(lambda r: httpx.Response(404), lambda c: fetch_page(c, "o/r", 1)) is None


def test_fetch_page_sends_api_version_header():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json=[])

    run(handler, lambda c: fetch_page(c, "o/r", 1))
    assert seen["x-github-api-version"] == config.STAR_WEEKS_API_VERSION


def test_full_history_reuses_recent_page_and_keeps_zero_weeks(tmp_path):
    fake = FakeGitHub({"o/r": 1})
    fake.history_weeks = 40
    journal = Journal(tmp_path / "w.jsonl")
    recent = run(fake, lambda c: fetch_star_weeks(c, ["o/r"], journal, DAY, full=False))["o/r"]
    assert (recent.pages_fetched, recent.pages_total) == (1, 2)
    assert len(recent.weeks) == 30
    assert fake.calls["history"] == 1

    full = run(fake, lambda c: fetch_star_weeks(c, ["o/r"], journal, DAY, full=True))["o/r"]
    assert fake.calls["history"] == 2  # 第一页复用缓存，只新增第二页
    assert (full.pages_fetched, full.pages_total) == (2, 2)
    assert len(full.weeks) == 40
    starts = [w["week_start"] for w in full.weeks]
    assert starts == sorted(starts)
    assert all(b - a == timedelta(days=7) for a, b in zip(starts, starts[1:], strict=False))


def test_non_contiguous_pages_are_rejected(tmp_path):
    fake = FakeGitHub({"o/r": 1})
    fake.history_weeks = 40
    original = fake.history

    def gap(request):
        response = original(request)
        if request.url.params["page"] == "2":
            rows = [{**r, "week": r["week"] - 7 * 86400} for r in response.json()]
            return httpx.Response(200, json=rows)
        return response

    fake.history = gap
    with pytest.raises(GitHubError, match="不连续"):
        run(
            fake,
            lambda c: fetch_star_weeks(c, ["o/r"], Journal(tmp_path / "w.jsonl"), DAY, full=True),
        )


def test_graphql_gateway_timeouts_split_the_batch():
    fake = FakeGitHub({"a/one": 1, "b/two": 2, "c/three": 3, "d/four": 4})
    original = fake.graphql

    def timeout_when_big(request):
        if request.content.count(b"repository(") > 1:  # 多个仓库的查询超时，单个正常
            return httpx.Response(502)
        return original(request)

    fake.graphql = timeout_when_big
    nodes = run(fake, lambda c: graphql.fetch_batch(c, ["a/one", "b/two", "c/three", "d/four"]))
    assert {n["nameWithOwner"] for n in nodes.values()} == {"a/one", "b/two", "c/three", "d/four"}


@pytest.mark.parametrize("status", [409, 451])
def test_unavailable_repository_statuses_are_not_fatal(status):
    assert run(lambda r: httpx.Response(status), lambda c: count_contributors(c, "o/r")) is None
    assert run(lambda r: httpx.Response(status), lambda c: fetch_page(c, "o/r", 1)) is None
