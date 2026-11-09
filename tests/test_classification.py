"""项目分类：校验、与总榜对齐、导出。"""

import json

import pytest
from conftest import classification_row, taxonomy, write_classification, write_dataset

from hot_repos import classification, config, export_web, store
from hot_repos.validate import validate

# ---------- 校验 ----------


def test_no_classification_is_valid(dataset):
    assert validate(dataset) == []


def test_valid_classification(dataset):
    write_classification(dataset)
    assert validate(dataset) == []


def test_both_files_must_exist_together(dataset):
    write_classification(dataset)
    (dataset / config.TAXONOMY_FILE).unlink()
    assert any(config.TAXONOMY_FILE in p and "必须同时存在" in p for p in validate(dataset))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"category": "nope"}, "category 不在目录中"),
        ({"related": ["nope"]}, "related 不在目录中"),
        ({"related": ["ai", "ai"]}, "related 有重复"),
        ({"related": ["dev.tools.cli"]}, "包含主分类"),
        ({"forms": ["app", "app"]}, "forms 有重复"),
        ({"forms": ["nope"]}, "forms"),
        ({"summary": " "}, "summary 为空"),
        ({"review_reason": ""}, "review_reason 为空字符串"),
    ],
)
def test_row_problems(dataset, change, message):
    write_classification(dataset, [classification_row("a/one", **change)])
    assert any(message in p for p in validate(dataset))


def test_names_must_match_repos_exactly(dataset):
    write_classification(dataset, [classification_row("A/One")])
    assert any("不在 repos.parquet 中" in p for p in validate(dataset))
    write_classification(dataset, [classification_row("x/other")])
    assert any("不在 repos.parquet 中" in p for p in validate(dataset))


def test_duplicate_names_ignoring_case(dataset):
    write_classification(dataset, [classification_row("a/one"), classification_row("a/ONE")])
    assert any("重复" in p for p in validate(dataset))


def test_taxonomy_problems(dataset):
    def check(nodes, message):
        write_classification(dataset, tax=taxonomy() | {"nodes": nodes})
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


def test_taxonomy_note_is_optional_but_not_blank(dataset):
    tax = taxonomy()
    del tax["note"]
    write_classification(dataset, tax=tax)
    assert validate(dataset) == []
    write_classification(dataset, tax=tax | {"note": " "})
    assert any("note 应为非空字符串" in p for p in validate(dataset))


# ---------- 与总榜对齐 ----------


def test_reconcile_renames_and_drops():
    rows = [
        classification_row("old/name"),
        classification_row("gone/repo"),
        classification_row("keep/Same"),
    ]
    kept, renamed, dropped = classification.reconcile(
        rows, ["new/name", "keep/Same"], {"new/name": ["new/name", "old/name"]}
    )
    assert [r["full_name"] for r in kept] == ["new/name", "keep/Same"]
    assert (renamed, dropped) == (1, ["gone/repo"])


def test_reconcile_uses_the_repos_spelling_and_keeps_one_row_per_repo():
    rows = [classification_row("A/One"), classification_row("a/one"), classification_row("x/y")]
    kept, renamed, dropped = classification.reconcile(rows, ["a/one"], {})
    assert [r["full_name"] for r in kept] == ["a/one"]
    assert renamed == 1
    assert dropped == ["a/one", "x/y"]


def test_publish_copies_optional_classification_files(tmp_path):
    staging = write_dataset(tmp_path / "staging")
    write_classification(staging)
    target = tmp_path / "target"
    store.publish(staging, target)
    assert (target / config.CLASSIFICATION_FILE).exists()
    assert (target / config.TAXONOMY_FILE).exists()


# ---------- 导出 ----------


def test_export_classification(dataset, tmp_path):
    write_classification(dataset, [classification_row("b/two", review_reason="边界不清")])
    out = tmp_path / "web"
    export_web.export(dataset, out)
    cls = export_web.read(out / "classification.json")
    assert cls["nodes"] == [
        ["dev", -1, "开发"],
        ["dev.tools", 0, "工具"],
        ["dev.tools.cli", 1, "命令行"],
        ["ai", -1, "人工智能"],
    ]
    assert cls["note"] == "测试说明"
    assert cls["forms"] == [["app", "应用"], ["list", "资源清单"]]
    # 列与 repos.json 对齐：a/one 未分类，b/two 已分类
    assert cls["category"] == [None, 2]
    assert cls["related"] == [[], [3]]
    assert cls["form"] == [[], [0]]
    details = export_web.read(out / "details.json")
    assert details["summary"] == [None, "一个工具"]
    assert details["review_reason"] == [None, "边界不清"]
    meta = export_web.read(out / "meta.json")
    assert meta["classified"] == 1


def test_export_without_classification_removes_stale_file(dataset, tmp_path):
    out = tmp_path / "web"
    write_classification(dataset)
    export_web.export(dataset, out)
    assert (out / "classification.json").exists()
    (dataset / config.CLASSIFICATION_FILE).unlink()
    (dataset / config.TAXONOMY_FILE).unlink()
    export_web.export(dataset, out)
    assert not (out / "classification.json").exists()
    meta = export_web.read(out / "meta.json")
    assert meta["classified"] == 0
    details = json.loads((out / "details.json").read_text(encoding="utf-8"))
    assert details["summary"] == [None, None]
