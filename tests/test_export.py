from datetime import UTC, date, datetime

import pytest
from conftest import repo_row, snapshot_rows, write_dataset, write_trending

from hot_repos import config, export_web
from hot_repos.export_web import (
    DETAIL_COLUMNS,
    REPO_COLUMNS,
    REPO_FLAGS,
    TRENDING_COLUMNS,
    ExportError,
    export,
    read,
)


def test_export_writes_aligned_columns(dataset, tmp_path):
    out = tmp_path / "web"
    export(dataset, out)
    repos, details, weeks = (read(out / f) for f in ("repos.json", "details.json", "weeks.json"))
    assert set(repos) == {*REPO_COLUMNS, *REPO_FLAGS}
    assert set(details) == set(DETAIL_COLUMNS)
    assert {len(v) for v in repos.values()} == {2}
    assert {len(v) for v in details.values()} == {2}
    assert [len(weeks["week_start"]), len(weeks["stars"])] == [2, 2]
    assert repos["rank"] == [1, 3]  # 名次可以不连续
    assert repos["full_name"] == ["a/one", "b/two"]


def test_timestamps_are_unix_seconds_and_missing_is_null(dataset, tmp_path):
    out = tmp_path / "web"
    export(dataset, out)
    repos, details = read(out / "repos.json"), read(out / "details.json")
    assert repos["created_at"][0] == 1577836800  # 2020-01-01T00:00:00Z
    assert repos["description"] == [None, None]
    assert details["homepage"] == [None, None]
    assert repos["has_homepage"] == [False, False]
    assert repos["has_readme"] == [True, True]
    assert repos["has_funding"] == [False, False]


def test_weeks_only_for_repos_that_have_them(dataset, tmp_path):
    out = tmp_path / "web"
    export(dataset, out)
    weeks = read(out / "weeks.json")
    assert weeks["week_start"] == ["2026-01-04", None]
    assert weeks["stars"] == [[7, 0], None]


def test_languages_and_funding_become_pairs(tmp_path):
    a = repo_row("a/one", 1, 200) | {"funding": [{"platform": "GITHUB", "url": "https://x"}]}
    export(write_dataset(tmp_path / "d", repos=[a, repo_row("b/two", 3, 100)]), tmp_path / "web")
    details = read(tmp_path / "web" / "details.json")
    assert details["languages"][0] == [["Python", 100]]
    assert details["funding"][0] == [["GITHUB", "https://x"]]
    assert read(tmp_path / "web" / "repos.json")["has_funding"] == [True, False]


def test_meta(dataset, tmp_path):
    export(dataset, tmp_path / "web")
    meta = read(tmp_path / "web" / "meta.json")
    assert meta["snapshot_date"] == "2026-01-10"
    assert (meta["repos"], meta["board_size"], meta["missing"]) == (2, 3, 1)
    assert meta["repos_fetched_at"] == [1768046400, 1768046400]


def test_no_trending_file_without_snapshots(dataset, tmp_path):
    out = tmp_path / "web"
    out.mkdir()
    (out / "trending.json").write_text("{}")  # 以前导出的旧文件
    export(dataset, out)
    assert not (out / "trending.json").exists()
    assert read(out / "meta.json")["trending_date"] is None


def test_trending_exports_only_the_latest_snapshot(dataset, tmp_path):
    directory = dataset / config.TRENDING_DIR_NAME
    older = [r | {"snapshot_date": date(2026, 1, 9)} for r in snapshot_rows()]
    older = [r | {"captured_at": datetime(2026, 1, 9, 1, tzinfo=UTC)} for r in older]
    write_trending(directory, older, "2026-01-09.parquet")
    rows = snapshot_rows() + [
        r | {"language": "c++", "full_name": f"x/{r['rank']}"} for r in snapshot_rows()
    ]
    write_trending(directory, rows)
    export(dataset, tmp_path / "web")
    page = read(tmp_path / "web" / "trending.json")
    assert read(tmp_path / "web" / "meta.json")["trending_date"] == "2026-01-10"
    assert page["snapshot_date"] == "2026-01-10"
    assert page["captured_at"] == 1768046400
    assert page["languages"] == [["all", "全部语言"], ["c++", "C++"]]
    assert set(page["rows"]) == set(TRENDING_COLUMNS)
    assert {len(v) for v in page["rows"].values()} == {len(rows)}
    assert page["rows"]["built_by"][0] == []


def test_trending_language_missing_from_config_keeps_its_key(dataset, tmp_path):
    rows = snapshot_rows() + [r | {"language": "zig"} for r in snapshot_rows()]
    write_trending(dataset / config.TRENDING_DIR_NAME, rows)
    export(dataset, tmp_path / "web")
    assert read(tmp_path / "web" / "trending.json")["languages"][-1] == ["zig", "zig"]


def test_invalid_data_is_not_exported(tmp_path):
    bad = [repo_row("a/one", 1, 200), repo_row("b/two", 1, 100)]  # 名次重复
    with pytest.raises(ExportError, match="rank 重复"):
        export(write_dataset(tmp_path / "d", repos=bad), tmp_path / "web")
    assert not (tmp_path / "web").exists()


def test_every_exported_column_exists_in_schema():
    from hot_repos import schema

    assert set(REPO_COLUMNS) <= set(schema.REPOS.names)
    assert set(DETAIL_COLUMNS) <= set(schema.REPOS.names)
    assert export_web.META_FILE == "meta.json"


def test_web_types_match_exported_columns():
    """web/src/data/types.ts 中各接口的字段必须与导出的列一致。"""
    import re

    from hot_repos import config

    source = (config.ROOT / "web" / "src" / "data" / "types.ts").read_text(encoding="utf-8")

    def fields(interface: str) -> list[str]:
        body = re.search(rf"export interface {interface} \{{\n(.*?)\n\}}", source, re.S)
        assert body, interface
        return re.findall(r"^  (\w+):", body.group(1), re.M)

    assert fields("RepoColumns") == [*REPO_COLUMNS, *REPO_FLAGS]
    assert fields("DetailColumns") == DETAIL_COLUMNS
    assert fields("WeeksColumns") == ["week_start", "stars"]
    assert fields("TrendingColumns") == TRENDING_COLUMNS
    assert fields("TrendingFile") == ["snapshot_date", "captured_at", "languages", "rows"]
    assert fields("Meta")[-1] == "trending_date"
