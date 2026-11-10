"""分类体系：校验、与总榜对齐、导出。"""

import json

import pytest
from conftest import external_meta, label_row, scheme_meta, write_dataset, write_scheme

from hot_repos import config, export_web, schemes, store
from hot_repos.validate import validate

# ---------- 校验 ----------


def test_no_schemes_is_valid(dataset):
    assert validate(dataset) == []


def test_valid_scheme(dataset):
    write_scheme(dataset)
    assert validate(dataset) == []


def test_labels_need_a_definition(dataset):
    write_scheme(dataset)
    (schemes.scheme_dir(dataset, "site") / config.SCHEME_META_FILE).unlink()
    assert any(config.SCHEME_META_FILE in p and "必须有体系定义" in p for p in validate(dataset))


def test_a_definition_can_exist_before_any_labels(dataset):
    write_scheme(dataset)
    (schemes.scheme_dir(dataset, "site") / config.SCHEME_LABELS_FILE).unlink()
    assert validate(dataset) == []
    schemes.write_meta(dataset, "site", scheme_meta(nodes=[]))
    assert any("nodes 应为非空列表" in p for p in validate(dataset))


def test_scheme_ids_are_slugs(dataset):
    write_scheme(dataset, scheme_id="Bad_Id")
    assert any("体系编号只能含" in p for p in validate(dataset))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"category": "nope"}, "category 不在体系中"),
        ({"category": None}, "category 不在体系中"),
        ({"related": ["nope"]}, "related 不在体系中"),
        ({"related": ["ai", "ai"]}, "related 有重复"),
        ({"related": ["dev.tools.cli"]}, "包含主分类"),
        ({"forms": ["app", "app"]}, "forms 有重复"),
        ({"forms": ["nope"]}, "forms"),
        ({"summary": " "}, "summary 为空字符串"),
        ({"review_reason": ""}, "review_reason 为空字符串"),
    ],
)
def test_row_problems(dataset, change, message):
    write_scheme(dataset, [label_row("a/one", **change)])
    assert any(message in p for p in validate(dataset))


def test_rows_without_a_primary_category(dataset):
    meta = external_meta()
    ok = label_row("a/one", category=None, related=["ai"], forms=[], summary=None)
    write_scheme(dataset, [ok], meta, "ext")
    assert validate(dataset) == []
    write_scheme(dataset, [ok | {"category": "ai", "related": []}], meta, "ext")
    assert any("category 应为空" in p for p in validate(dataset))
    write_scheme(dataset, [ok | {"related": []}], meta, "ext")
    assert any("没有任何分类" in p for p in validate(dataset))


def test_names_must_match_repos_exactly(dataset):
    write_scheme(dataset, [label_row("A/One")])
    assert any("不在 repos.parquet 中" in p for p in validate(dataset))
    write_scheme(dataset, [label_row("x/other")])
    assert any("不在 repos.parquet 中" in p for p in validate(dataset))


def test_duplicate_names_ignoring_case(dataset):
    write_scheme(dataset, [label_row("a/one"), label_row("a/ONE")])
    assert any("重复" in p for p in validate(dataset))


def test_node_problems(dataset):
    def check(nodes, message):
        write_scheme(dataset, meta=scheme_meta(nodes=nodes))
        assert any(message in p for p in validate(dataset)), message

    check([{"id": "a", "label": "甲"}, {"id": "a", "label": "乙"}], "编号重复")
    check(
        [{"id": "a.b", "label": "甲", "parent": "a"}, {"id": "a", "label": "乙"}],
        "不存在或排在它之后",
    )
    check(
        [{"id": "a", "label": "甲"}, {"id": "b.c", "label": "乙", "parent": "a"}], "应以父节点编号"
    )
    check([{"id": "a.b", "label": "甲"}], "不应含")
    check(
        [
            {"id": "a", "label": "甲"},
            {"id": "a.x", "label": "乙", "parent": "a"},
            {"id": "a.y", "label": "乙", "parent": "a"},
        ],
        "名称重复",
    )
    check([], "nodes 应为非空列表")


def test_forms_and_guidance_need_text(dataset):
    def check(change, message):
        meta = scheme_meta()
        change(meta)
        write_scheme(dataset, meta=meta)
        assert any(message in p for p in validate(dataset)), message

    check(lambda t: t["forms"].update(app={"label": "应用"}), "forms 应为")
    check(lambda t: t["forms"].update(app={"label": "应用", "definition": " "}), "forms 应为")
    check(lambda t: t["nodes"][0].update(guidance={"excludes": "x"}), "guidance 应为")
    check(lambda t: t["nodes"][0].update(guidance={"includes": ""}), "guidance 应为")
    check(lambda t: t["nodes"][0].update(guidance={"includes": "x", "other": "y"}), "guidance 应为")


def test_meta_fields(dataset):
    def check(meta, message):
        write_scheme(dataset, meta=meta)
        assert any(message in p for p in validate(dataset)), message

    check(scheme_meta(name=" "), "name 应为非空字符串")
    check(scheme_meta(summary=""), "summary 应为非空字符串")
    check(scheme_meta(method="guess"), "method 应为")
    check(scheme_meta(primary="yes"), "primary 应为")
    check(scheme_meta(order="1"), "order 应为整数")
    check(scheme_meta(note=" "), "note 应为非空字符串")
    check(scheme_meta(as_of="2026-01-01"), "不应有 as_of")
    check(scheme_meta(created="去年"), "created 应为日期")
    check(scheme_meta(updated=None), "updated 应为日期")
    check(scheme_meta(created="2026-02-01"), "created 不应晚于 updated")


def test_note_and_forms_are_optional(dataset):
    meta = scheme_meta()
    del meta["note"], meta["forms"]
    write_scheme(dataset, [label_row("a/one", forms=[])], meta)
    assert validate(dataset) == []


def test_external_schemes_need_a_source_and_date(dataset):
    def check(change, message):
        meta = external_meta()
        change(meta)
        write_scheme(dataset, [label_row("a/one", category=None, forms=[])], meta, "ext")
        assert any(message in p for p in validate(dataset)), message

    check(lambda m: m.pop("source"), "source 应为")
    check(lambda m: m["source"].update(url="ftp://x"), "source 应为")
    check(lambda m: m["source"].update(license=""), "source 应为")
    check(lambda m: m["source"].update(extra="x"), "source 应为")
    check(lambda m: m.pop("as_of"), "as_of")
    check(lambda m: m.update(as_of="昨天"), "as_of")


# ---------- 与总榜对齐 ----------


def test_reconcile_renames_and_drops():
    rows = [label_row("old/name"), label_row("gone/repo"), label_row("keep/Same")]
    kept, renamed, dropped = schemes.reconcile(
        rows, ["new/name", "keep/Same"], {"new/name": ["new/name", "old/name"]}
    )
    assert [r["full_name"] for r in kept] == ["new/name", "keep/Same"]
    assert (renamed, dropped) == (1, ["gone/repo"])


def test_reconcile_uses_the_repos_spelling_and_keeps_one_row_per_repo():
    rows = [label_row("A/One"), label_row("a/one"), label_row("x/y")]
    kept, renamed, dropped = schemes.reconcile(rows, ["a/one"], {})
    assert [r["full_name"] for r in kept] == ["a/one"]
    assert renamed == 1
    assert dropped == ["a/one", "x/y"]


def test_build_rows_and_prune_nodes():
    members = {"a/one": ["x.b", "y", "x.b"], "b/two": ["y"]}
    assert schemes.build_rows(members, True)[0] == {
        "full_name": "a/one",
        "category": "x.b",
        "related": ["y"],
        "forms": [],
        "summary": None,
        "review_reason": None,
    }
    flat = schemes.build_rows(members, False)
    assert (flat[0]["category"], flat[0]["related"]) == (None, ["x.b", "y"])
    nodes = [
        {"id": "x", "label": "X"},
        {"id": "x.a", "label": "A", "parent": "x"},
        {"id": "x.b", "label": "B", "parent": "x"},
        {"id": "y", "label": "Y"},
        {"id": "z", "label": "Z"},
    ]
    assert [n["id"] for n in schemes.prune_nodes(nodes, {"x.b", "y"})] == ["x", "x.b", "y"]


def test_scheme_ids_follow_order_then_id(dataset):
    write_scheme(dataset, meta=scheme_meta(order=5), scheme_id="zeta")
    write_scheme(dataset, meta=scheme_meta(), scheme_id="alpha")
    write_scheme(dataset, meta=scheme_meta(order=0), scheme_id="site")
    assert schemes.scheme_ids(dataset) == ["site", "zeta", "alpha"]


def test_publish_copies_scheme_files(tmp_path):
    staging = write_dataset(tmp_path / "staging")
    write_scheme(staging)
    target = tmp_path / "target"
    store.publish(staging, target)
    folder = schemes.scheme_dir(target, "site")
    assert (folder / config.SCHEME_LABELS_FILE).exists()
    assert (folder / config.SCHEME_META_FILE).exists()


# ---------- 导出 ----------


def test_export_scheme(dataset, tmp_path):
    write_scheme(dataset, [label_row("b/two", review_reason="边界不清")])
    out = tmp_path / "web"
    export_web.export(dataset, out)
    scheme = export_web.read(out / "scheme-site.json")
    assert scheme["nodes"] == [
        ["dev", -1, "开发", "写代码的工具", None],
        ["dev.tools", 0, "工具", "命令行与编辑器", "数据库归 data"],
        ["dev.tools.cli", 1, "命令行", None, None],
        ["ai", -1, "人工智能", None, None],
    ]
    assert scheme["forms"] == [
        ["app", "应用", "直接使用的应用"],
        ["list", "资源清单", "收集链接的清单"],
    ]
    # 列与 repos.json 对齐：a/one 没有标注，b/two 已标注
    assert scheme["category"] == [None, 2]
    assert scheme["related"] == [[], [3]]
    assert scheme["form"] == [[], [0]]
    text = export_web.read(out / "details.json")["scheme_text"]
    assert text == {"site": {"summary": [None, "一个工具"], "review_reason": [None, "边界不清"]}}
    [info] = export_web.read(out / "meta.json")["schemes"]
    assert info == {
        "id": "site",
        "name": "测试体系",
        "summary": "用于测试的体系",
        "method": "model",
        "source": None,
        "created": "2026-01-01",
        "updated": "2026-01-09",
        "as_of": None,
        "note": "测试说明",
        "primary": True,
        "classified": 1,
    }


def test_export_scheme_without_primary(dataset, tmp_path):
    rows = [
        label_row("a/one", category=None, related=["dev.tools.cli", "ai"], forms=[], summary=None)
    ]
    write_scheme(dataset, rows, external_meta(), "ext")
    out = tmp_path / "web"
    export_web.export(dataset, out)
    scheme = export_web.read(out / "scheme-ext.json")
    assert scheme["category"] == [None, None]
    assert scheme["related"] == [[2, 3], []]
    assert scheme["forms"] == []
    [info] = export_web.read(out / "meta.json")["schemes"]
    assert (info["primary"], info["classified"], info["source"]["license"]) == (
        False,
        1,
        "CC-BY-4.0",
    )
    assert export_web.read(out / "details.json")["scheme_text"] == {}  # 没有简介，不列出


def test_export_lists_schemes_in_order_and_skips_ones_without_labels(dataset, tmp_path):
    write_scheme(dataset, meta=scheme_meta(order=2), scheme_id="second")
    write_scheme(dataset, meta=scheme_meta(order=1), scheme_id="first")
    schemes.write_meta(dataset, "empty", scheme_meta())
    out = tmp_path / "web"
    export_web.export(dataset, out)
    assert [s["id"] for s in export_web.read(out / "meta.json")["schemes"]] == ["first", "second"]
    assert not (out / "scheme-empty.json").exists()


def test_export_without_schemes_removes_stale_files(dataset, tmp_path):
    out = tmp_path / "web"
    write_scheme(dataset)
    export_web.export(dataset, out)
    assert (out / "scheme-site.json").exists()
    (schemes.scheme_dir(dataset, "site") / config.SCHEME_LABELS_FILE).unlink()
    export_web.export(dataset, out)
    assert not (out / "scheme-site.json").exists()
    assert export_web.read(out / "meta.json")["schemes"] == []
    details = json.loads((out / "details.json").read_text(encoding="utf-8"))
    assert details["scheme_text"] == {}
