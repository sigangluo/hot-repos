import asyncio
import re
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import snapshot_rows, write_trending

from hot_repos import config, trending, validate
from hot_repos.github.client import GitHubClient
from hot_repos.github.trending import TrendingError, fetch_page, page_url, parse_page

DATA = Path(__file__).parent / "data"
NOW = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


async def no_sleep(_):
    pass


def article(
    name: str,
    *,
    desc: str | None = "描述",
    lang: str | None = "Python",
    stars: int = 100,
    forks: int = 5,
    period: int = 10,
    unit: str = "today",
    built_by: tuple[str, ...] = ("alice", "bob"),
) -> str:
    owner, repo = name.split("/")
    avatars = "".join(
        f'<a href="/{u}"><img class="avatar avatar-user" src="x" alt="@{u}" /></a>'
        for u in built_by
    )
    return f"""<article class="Box-row">
<h2 class="h3 lh-condensed"><a href="/{name}" class="Link">
<span class="text-normal">{owner} /</span> {repo}</a></h2>
{f'<p class="col-9 color-fg-muted my-1">{desc}</p>' if desc is not None else ""}
<div class="f6">
{f'<span itemprop="programmingLanguage">{lang}</span>' if lang else ""}
<a href="/{name}/stargazers"><svg><path d=""></path></svg> {stars:,}</a>
<a href="/{name}/forks"><svg></svg> {forks:,}</a>
<span>Built by {avatars}</span>
<span class="float-sm-right"><svg></svg> {period:,} stars {unit}</span>
</div></article>"""


def page(
    articles: list[str], title: str = "Trending  repositories on GitHub today · GitHub"
) -> str:
    return f"<html><head><title>{title}</title></head><body>{''.join(articles)}</body></html>"


# ---------- 解析：真实页面样本 ----------


def test_parses_real_daily_page():
    entries = parse_page((DATA / "trending_daily.html").read_text(encoding="utf-8"), "daily")
    assert [e.full_name for e in entries] == [
        "anthropics/skills",
        "sherlock-project/sherlock",
        "homeassistant-ai/ha-mcp",
    ]
    first = entries[0]
    assert first.description == "Public repository for Agent Skills"
    assert first.language == "Python"
    assert (first.stars, first.forks, first.period_stars) == (190258, 22397, 1052)
    assert first.built_by == ("rlancemartin", "klazuka", "claude", "cj-ant", "ericharmeling")
    # 机器人账号在页面里同样是 Built by 头像，原样保留
    assert entries[2].built_by == (
        "github-actions",
        "claude",
        "kingpanther13",
        "julienld",
        "dependabot",
    )


def test_parses_real_monthly_page_with_missing_description():
    entries = parse_page((DATA / "trending_monthly.html").read_text(encoding="utf-8"), "monthly")
    t3 = entries[0]
    assert t3.full_name == "pingdotgg/t3code"
    assert t3.description is None
    assert t3.language == "TypeScript"
    assert (t3.stars, t3.forks, t3.period_stars) == (53368, 10100, 25840)


# ---------- 解析：边界与失败 ----------


def test_missing_language_is_none():
    entry = parse_page(page([article("a/b", lang=None)]), "daily")[0]
    assert entry.language is None


def test_description_with_nested_tags_and_entities():
    html = page([article("a/b", desc='<g-emoji>🚀</g-emoji> fast &amp; <a href="#">small</a>')])
    assert parse_page(html, "daily")[0].description == "🚀 fast & small"


def test_empty_trending_page_is_valid():
    assert parse_page(page([]), "daily") == []


def test_duplicate_repo_is_kept_once():
    html = page([article("a/b", period=5), article("A/B", period=9), article("c/d")])
    assert [e.full_name for e in parse_page(html, "daily")] == ["a/b", "c/d"]


def test_rejects_page_that_is_not_trending():
    with pytest.raises(TrendingError, match="不是 Trending"):
        parse_page(page([article("a/b")], title="Sign in to GitHub"), "daily")


def test_rejects_mismatched_period():
    with pytest.raises(TrendingError, match="this week"):
        parse_page(page([article("a/b", unit="this week")]), "daily")


def test_rejects_entry_without_period_stars():
    html = page([article("a/b").replace("stars today", "")])
    with pytest.raises(TrendingError, match="新增 Star"):
        parse_page(html, "daily")


def test_rejects_entry_without_name():
    html = page([article("a/b").replace('href="/a/b" class="Link"', 'class="Link"')])
    with pytest.raises(TrendingError, match="仓库名"):
        parse_page(html, "daily")


def test_rejects_unparseable_counts():
    html = page([article("a/b").replace("100", "many", 1)])
    with pytest.raises(TrendingError, match="stars"):
        parse_page(html, "daily")


def test_rejects_unknown_period():
    with pytest.raises(ValueError):
        parse_page(page([]), "yearly")


# ---------- 抓取 ----------


def test_page_urls():
    assert page_url("all") == "https://github.com/trending"
    assert page_url("python") == "https://github.com/trending/python"
    assert page_url("c++") == "https://github.com/trending/c%2B%2B"
    assert page_url("c#") == "https://github.com/trending/c%23"


def make_site(entries: int = 6, fail: set[tuple[str, str]] | None = None):
    """模拟 Trending：每个（语言，时间段）返回 `entries` 条，记录收到的请求。"""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.raw_path.decode().split("?")[0]
        language = path.removeprefix("/trending").strip("/") or "all"
        since = request.url.params["since"]
        if fail and (language, since) in fail:
            return httpx.Response(404)
        tag = re.sub(r"\W", "_", language)
        unit = config.TRENDING_PERIODS[since]
        items = [
            article(f"o{i}/{tag}-{since}", unit=unit, period=100 - i, stars=1000 - i)
            for i in range(entries)
        ]
        # 同一榜单里仓库名要互不相同
        items = [a.replace(f"-{since}", f"-{since}{i}") for i, a in enumerate(items)]
        return httpx.Response(200, text=page(items))

    return handler, seen


def client_for(handler) -> GitHubClient:
    return GitHubClient(None, rps=1e6, transport=httpx.MockTransport(handler), sleep=no_sleep)


def run(handler, trending_dir: Path, **kwargs) -> Path:
    async def go():
        async with client_for(handler) as c:
            return await trending.run(c, trending_dir, now=NOW, **kwargs)

    return asyncio.run(go())


def test_fetch_page_sends_period_and_no_credentials():
    handler, seen = make_site()

    async def go():
        async with client_for(handler) as c:
            return await fetch_page(c, "weekly", "c++")

    entries = asyncio.run(go())
    assert len(entries) == 6
    request = seen[0]
    assert request.url.raw_path.decode() == "/trending/c%2B%2B?since=weekly"
    assert "authorization" not in request.headers
    assert request.headers["user-agent"] == "hot-repos"


def test_fetch_page_reports_http_errors():
    handler, _ = make_site(fail={("rust", "daily")})

    async def go():
        async with client_for(handler) as c:
            return await fetch_page(c, "daily", "rust")

    with pytest.raises(TrendingError, match="404"):
        asyncio.run(go())


# ---------- 整天快照 ----------


def test_run_writes_a_valid_complete_snapshot(tmp_path):
    handler, seen = make_site()
    path = run(handler, tmp_path / "trending", languages=("python", "c++"))
    assert path.name == "2026-01-10.parquet"
    assert len(seen) == 3 * 3  # 全部语言 + 2 种语言，各 3 个时间段
    rows = trending.read_snapshot(path)
    assert len(rows) == 9 * 6
    assert validate.validate_trending(tmp_path / "trending") == []
    top = next(r for r in rows if (r["since"], r["language"], r["rank"]) == ("weekly", "c++", 1))
    assert re.fullmatch(r"o0/c_2B_2B-weekly0", top["full_name"])  # 地址里的 c%2B%2B 来自 c++
    assert top["captured_at"] == NOW
    assert top["built_by"] == ["alice", "bob"]


def test_rerun_on_same_day_replaces_the_file(tmp_path):
    directory = tmp_path / "trending"
    run(make_site(entries=6)[0], directory, languages=())
    run(make_site(entries=8)[0], directory, languages=())
    assert [p.name for p in trending.snapshot_files(directory)] == ["2026-01-10.parquet"]
    assert len(trending.read_snapshot(directory / "2026-01-10.parquet")) == 3 * 8


def test_too_few_entries_in_the_all_list_writes_nothing(tmp_path):
    handler, _ = make_site(entries=config.TRENDING_MIN_ENTRIES - 1)
    with pytest.raises(TrendingError, match="页面结构可能变了"):
        run(handler, tmp_path / "trending", languages=())
    assert not (tmp_path / "trending").exists()


def test_a_failed_page_writes_nothing(tmp_path):
    directory = tmp_path / "trending"
    run(make_site()[0], directory, languages=())
    before = (directory / "2026-01-10.parquet").read_bytes()
    handler, _ = make_site(fail={("python", "monthly")})
    with pytest.raises(TrendingError):
        run(handler, directory, languages=("python",))
    assert (directory / "2026-01-10.parquet").read_bytes() == before  # 当天原有的文件不受影响
    assert not list(directory.glob("*.tmp"))


def test_language_list_may_be_empty_for_a_language(tmp_path, caplog):
    def handler(request):
        language = request.url.raw_path.decode().removeprefix("/trending").split("?")[0].strip("/")
        if language == "swift":
            return httpx.Response(200, text=page([]))
        return make_site()[0](request)

    run(handler, tmp_path / "trending", languages=("swift",))
    assert "没有上榜项目" in caplog.text
    rows = trending.read_snapshot(tmp_path / "trending" / "2026-01-10.parquet")
    assert {r["language"] for r in rows} == {"all"}


# ---------- 校验 ----------


def problems_for(tmp_path: Path, rows: list[dict], name: str = "2026-01-10.parquet") -> str:
    write_trending(tmp_path, rows, name)
    return "\n".join(validate.validate_trending(tmp_path))


def test_validation_passes_on_a_good_snapshot(tmp_path):
    assert problems_for(tmp_path, snapshot_rows()) == ""


def test_validation_ignores_a_missing_directory(tmp_path):
    assert validate.validate_trending(tmp_path / "nope") == []


def test_validation_rejects_bad_file_names(tmp_path):
    assert "文件名" in problems_for(tmp_path, snapshot_rows(), "latest.parquet")
    assert "文件名" in problems_for(tmp_path, snapshot_rows(), "2026-13-45.parquet")


def test_validation_rejects_date_mismatch(tmp_path):
    assert "snapshot_date" in problems_for(tmp_path, snapshot_rows(snapshot_date=date(2026, 1, 9)))
    other = datetime(2026, 1, 9, 23, tzinfo=UTC)
    assert "captured_at 的日期" in problems_for(tmp_path, snapshot_rows(captured_at=other))


def test_validation_rejects_gaps_and_duplicates(tmp_path):
    rows = snapshot_rows()
    rows[1] = rows[1] | {"rank": 3}
    assert "rank 应从 1 开始连续" in problems_for(tmp_path, rows)
    rows = snapshot_rows()
    rows[1] = rows[1] | {"full_name": "O1/R"}
    assert "full_name 重复" in problems_for(tmp_path, rows)


def test_validation_requires_every_period_for_all_languages(tmp_path):
    rows = [r for r in snapshot_rows() if r["since"] != "weekly"]
    assert "缺少「全部语言」的 weekly" in problems_for(tmp_path, rows)


def test_validation_rejects_negative_counts_and_bad_names(tmp_path):
    assert "period_stars 为负数" in problems_for(tmp_path, snapshot_rows(period_stars=-1))
    assert "owner/repo" in problems_for(tmp_path, snapshot_rows(full_name="norepo"))


def test_validation_rejects_wrong_schema(tmp_path):
    pq.write_table(pa.table({"x": [1]}), tmp_path / "2026-01-10.parquet")
    assert "表结构" in "\n".join(validate.validate_trending(tmp_path))


def test_main_validation_includes_trending(dataset):
    write_trending(dataset / config.TRENDING_DIR_NAME, snapshot_rows(rank=1))
    assert any("trending/2026-01-10.parquet" in p for p in validate.validate(dataset))
