"""同步外部分类体系：对上总榜、写入、失败时保留旧数据、没有变化时不重写。"""

from datetime import date

import pytest

from hot_repos import cli, config, schemes, sync
from hot_repos.sources import Collected, Fetcher, SourceError
from hot_repos.validate import validate


def collected(members=None, **changes) -> Collected:
    meta = {
        "name": "假来源",
        "summary": "测试用的假来源",
        "method": "curated",
        "primary": False,
        "source": {"name": "某来源", "url": "https://example.com", "license": "MIT"},
        "nodes": [
            {"id": "web", "label": "Web"},
            {"id": "db", "label": "Database"},
            {"id": "unused", "label": "没人用"},
        ],
    } | changes
    return Collected(meta, members or {"A/One": ["web", "db"], "gone/repo": ["web"]})


@pytest.fixture
def fake_source(monkeypatch):
    """登记一个假来源 fake；返回可替换其行为的字典。"""
    state = {"result": collected()}

    def collect(_fetcher):
        if isinstance(state["result"], Exception):
            raise state["result"]
        return state["result"]

    monkeypatch.setattr(sync, "registry", lambda: {"fake": collect})
    return state


def run(dataset, ids=("fake",), today=date(2026, 3, 1)):
    return sync.run(dataset, list(ids), Fetcher(), today=today)


def test_match_ignores_case_and_follows_renames():
    matched = sync.match(
        {"A/One": ["x"], "old/name": ["y"], "nobody/home": ["z"], "a/one": ["w"]},
        ["a/one", "new/name"],
        {"new/name": ["new/name", "old/name"]},
    )
    assert matched == {"a/one": ["x", "w"], "new/name": ["y"]}


def test_sync_writes_matched_projects_and_used_nodes(dataset, fake_source):
    assert run(dataset) == {"fake": "1 个项目，2 个分类"}
    meta = schemes.read_meta(dataset, "fake")
    assert meta["as_of"] == "2026-03-01"
    assert [n["id"] for n in meta["nodes"]] == ["web", "db"]  # 没人用的节点不保存
    rows = schemes.read_rows(dataset, "fake")
    assert [(r["full_name"], r["category"], r["related"]) for r in rows] == [
        ("a/one", None, ["web", "db"])  # 用总榜里的写法；没有主分类的体系全部放在 related
    ]
    assert validate(dataset) == []


def test_sync_with_a_primary_category(dataset, fake_source):
    fake_source["result"] = collected(primary=True)
    run(dataset)
    [row] = schemes.read_rows(dataset, "fake")
    assert (row["category"], row["related"]) == ("web", ["db"])


def test_roots_do_not_carry_a_null_parent(dataset, fake_source):
    nodes = [{"id": "web", "label": "Web", "parent": None}]
    fake_source["result"] = collected({"a/one": ["web"]}, nodes=nodes)
    run(dataset)
    assert schemes.read_meta(dataset, "fake")["nodes"] == [{"id": "web", "label": "Web"}]


def test_unchanged_source_is_not_rewritten(dataset, fake_source):
    run(dataset)
    path = schemes.scheme_dir(dataset, "fake") / config.SCHEME_META_FILE
    before = path.read_text(encoding="utf-8")
    result = run(dataset, today=date(2026, 4, 1))
    assert "与上次相同" in result["fake"]
    assert path.read_text(encoding="utf-8") == before  # 取得日期也没有更新
    fake_source["result"] = collected({"A/One": ["web"]})
    run(dataset, today=date(2026, 4, 1))
    assert schemes.read_meta(dataset, "fake")["as_of"] == "2026-04-01"


def test_failure_keeps_existing_data_and_reports(dataset, fake_source):
    run(dataset)
    fake_source["result"] = SourceError("网络不通")
    assert run(dataset)["fake"] == "失败：网络不通"
    assert [r["full_name"] for r in schemes.read_rows(dataset, "fake")] == ["a/one"]


@pytest.mark.parametrize(
    ("members", "message"),
    [
        ({"nobody/home": ["web"]}, "没有一个对得上"),
        ({"a/one": ["nope"]}, "没有的分类"),
    ],
)
def test_unusable_sources_are_rejected(dataset, fake_source, members, message):
    fake_source["result"] = collected(members)
    assert message in run(dataset)["fake"]
    assert schemes.read_meta(dataset, "fake") is None


def test_invalid_results_are_rejected(dataset, fake_source):
    fake_source["result"] = collected({"a/one": ["web"]}, summary=" ")
    assert "未通过校验" in run(dataset)["fake"]


def test_unknown_source_and_missing_board(dataset, fake_source, tmp_path):
    with pytest.raises(SourceError, match="没有这个来源"):
        run(dataset, ids=("nope",))
    with pytest.raises(SourceError, match="还没有总榜"):
        sync.run(tmp_path / "empty", [], Fetcher())


def test_cli_exit_code_follows_failures(dataset, fake_source, capsys):
    assert cli.main(["schemes", "sync", "fake", "--data-dir", str(dataset)]) == 0
    assert "fake: 1 个项目" in capsys.readouterr().out
    fake_source["result"] = SourceError("坏了")
    assert cli.main(["schemes", "sync", "fake", "--data-dir", str(dataset)]) == 1
