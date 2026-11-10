"""外部分类来源的解析与取数测试：全部离线，用内联的小样本和 MockTransport。"""

import json
from datetime import date

import httpx
import pytest

from hot_repos import sync
from hot_repos.sources import Fetcher, SourceError, borges, explore, landscape, ossinsight, registry
from hot_repos.validate import check_scheme_meta

BORGES_CSV = (
    "\ufeffName,Stars,Forks,Language,Description,URL,Domain,Growth Pattern\n"
    'twbs/bootstrap,105991,48185,JavaScript,"The framework, popular",https://github.com/twbs/bootstrap,Web libraries and frameworks,\n'
    "torvalds/linux,90000,30000,C,Linux kernel,https://github.com/torvalds/linux,System software,\n"
    "git/git,40000,20000,C,git,https://github.com/git/git,Software tools,\n"
    "odd/domain,1,1,C,x,https://github.com/odd/domain,Something else,\n"
    "no/domain,1,1,C,x,https://github.com/no/domain,,\n"
    ",1,1,C,x,,Documentation,\n"
)

EXPLORE_ML = """---
items:
 - apache/spark
 - https://github.com/tensorflow/tensorflow.git
 - pytorch/pytorch/
 - https://www.youtube.com/embed/KsbQ_HNX6Pg
 - huggingface
 - apache/spark
display_name: Getting started with machine learning
created_by: omoju
---
Today, machine learning has found a new audience.
It spans many things.

Second paragraph is ignored.
"""
EXPLORE_EMPTY = (
    "---\nitems:\n - https://www.youtube.com/watch?v=x\ndisplay_name: Videos\n---\nOnly videos.\n"
)
EXPLORE_NO_NAME = "---\nitems:\n - apache/spark\n - vuejs/vue\n---\n"
EXPLORE_BAD = "no front matter here"

OSS_WEB = "id: 10004\nname: Web Framework\nitems:\n  - rails/rails\n  - django/django\n"
OSS_SSG = "id: 1\nname: Static Site Generator\nitems:\n  - jekyll/jekyll\n  - rails/rails\n"
OSS_EMPTY = "id: 3\nname: Nothing\nitems: []\n"

LANDSCAPE = """
landscape:
  - category:
    name: Provisioning
    subcategories:
      - subcategory:
        name: Automation & Configuration
        items:
          - item:
            name: Ansible
            repo_url: https://github.com/ansible/ansible
            additional_repos:
              - repo_url: https://github.com/ansible/ansible-lint/
          - item:
            name: A member company
            homepage_url: https://example.com
          - item:
            name: Hosted elsewhere
            repo_url: https://gitlab.com/foo/bar
          - item:
            name: Org only
            repo_url: https://github.com/someorg
      - subcategory:
        name: Security & Compliance
        items:
          - item:
            name: Ansible again
            repo_url: https://github.com/ansible/ansible.git
  - category:
    name: Runtime
    subcategories:
      - subcategory:
        name: Empty one
      - subcategory:
        name: Container Runtime
        items:
          - item:
            name: containerd
            repo_url: https://github.com/containerd/containerd
"""


def mock_fetcher(routes: dict[str, str | dict]) -> Fetcher:
    """按 URL 返回固定内容的取数器；没登记的 URL 返回 404。"""

    def handler(request: httpx.Request) -> httpx.Response:
        body = routes.get(str(request.url))
        if body is None:
            return httpx.Response(404)
        if isinstance(body, dict):
            return httpx.Response(200, json=body)
        return httpx.Response(200, text=body)

    return Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)


def tree(*paths: str, truncated: bool = False) -> dict:
    return {
        "truncated": truncated,
        "tree": [
            {"path": p, "type": "blob" if "." in p.rsplit("/", 1)[-1] else "tree"} for p in paths
        ],
    }


def assert_meta_valid(collected, as_of: str = "2026-01-01") -> None:
    meta = collected.meta | {"as_of": as_of}
    assert check_scheme_meta(meta, "scheme.json") == []
    ids = {n["id"] for n in meta["nodes"]}
    assert {i for v in collected.members.values() for i in v} <= ids


# ---- 共用工具 ----


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("apache/spark", "apache/spark"),
        ("lambda-client/lambda/", "lambda-client/lambda"),
        ("https://github.com/ClickHouse/ClickHouse", "ClickHouse/ClickHouse"),
        ("https://github.com/a/b.git", "a/b"),
        ("https://github.com/hyperopt/hyperopt/", "hyperopt/hyperopt"),
        ("http://www.github.com/a/b/tree/main/docs", "a/b"),
        ("github.com/a/b", "a/b"),
        ("https://github.com/nginx", None),
        ("huggingface", None),
        ("https://www.youtube.com/watch?v=x", None),
        ("https://gitlab.com/a/b", None),
        ("gitlab.com/a/b", None),
        ("", None),
        (None, None),
        (3, None),
    ],
)
def test_repo_name(value, expected):
    assert explore.repo_name(value) == expected


def test_slug_helpers():
    assert explore.slugify("Orchestration & Management") == "orchestration-management"
    assert explore.slugify("日本語") == "x"
    used: set[str] = set()
    assert [explore.unique_slug("a", used) for _ in range(3)] == ["a", "a-2", "a-3"]
    labels: set[str] = set()
    assert explore.unique_label("X", "x", labels) == "X"
    assert explore.unique_label("X", "x-2", labels) == "X (x-2)"


def test_first_paragraph_trims_long_text():
    assert explore.first_paragraph("\n\nHello\nworld.\n\nsecond") == "Hello world."
    assert explore.first_paragraph("   ") is None
    long = explore.first_paragraph("word " * 200)
    assert long is not None and long.endswith("…") and len(long) <= 301


# ---- borges ----


def test_parse_borges():
    collected = borges.parse_borges(BORGES_CSV)
    assert collected.members == {
        "twbs/bootstrap": ["web-libraries-and-frameworks"],
        "torvalds/linux": ["system-software"],
        "git/git": ["software-tools"],
    }
    meta = collected.meta
    assert meta["primary"] is True and meta["method"] == "manual" and meta["order"] == 30
    assert [n["label"] for n in meta["nodes"]] == [d[1] for d in borges.DOMAINS]
    assert meta["source"]["license"] == "CC-BY-4.0"
    assert "Borges" in meta["source"]["attribution"]
    assert_meta_valid(collected)


def test_parse_borges_rejects_unexpected_columns():
    with pytest.raises(SourceError, match="列"):
        borges.parse_borges("a,b\n1,2\n")


def test_collect_borges():
    collected = borges.collect(mock_fetcher({borges.CSV_URL: BORGES_CSV}))
    assert len(collected.members) == 3


def test_collect_borges_without_valid_rows():
    csv_text = "Name,Domain\nx/y,Unknown\n"
    with pytest.raises(SourceError, match="有效数据"):
        borges.collect(mock_fetcher({borges.CSV_URL: csv_text}))


# ---- explore ----


def test_parse_explore():
    collected = explore.parse_explore(
        {
            "machine-learning": EXPLORE_ML,
            "videos": EXPLORE_EMPTY,
            "no-name": EXPLORE_NO_NAME,
            "broken": EXPLORE_BAD,
        }
    )
    nodes = {n["id"]: n for n in collected.meta["nodes"]}
    assert list(nodes) == ["machine-learning", "no-name"]  # 没有项目、没有头的合集被略过
    assert nodes["machine-learning"]["label"] == "Getting started with machine learning"
    assert nodes["machine-learning"]["guidance"] == {
        "includes": "Today, machine learning has found a new audience. It spans many things."
    }
    assert nodes["no-name"]["label"] == "no-name" and "guidance" not in nodes["no-name"]
    assert collected.members == {
        "apache/spark": ["machine-learning", "no-name"],
        "tensorflow/tensorflow": ["machine-learning"],
        "pytorch/pytorch": ["machine-learning"],
        "vuejs/vue": ["no-name"],
    }
    assert collected.meta["primary"] is False and collected.meta["order"] == 10
    assert collected.meta["source"]["license"] == "CC-BY-4.0"
    assert_meta_valid(collected)


def test_parse_explore_disambiguates_labels():
    same = "---\nitems:\n - a/b\ndisplay_name: Same\n---\n"
    collected = explore.parse_explore({"one": same, "two": same})
    assert [n["label"] for n in collected.meta["nodes"]] == ["Same", "Same (two)"]
    assert_meta_valid(collected)


def test_collect_explore():
    fetcher = mock_fetcher(
        {
            "https://api.github.com/repos/github/explore/git/trees/main?recursive=1": tree(
                "collections",
                "collections/machine-learning",
                "collections/machine-learning/index.md",
                "collections/videos/index.md",
                "collections/machine-learning/image.png",
                "topics/python/index.md",
            ),
            "https://raw.githubusercontent.com/github/explore/main/collections/machine-learning/index.md": EXPLORE_ML,
            "https://raw.githubusercontent.com/github/explore/main/collections/videos/index.md": EXPLORE_EMPTY,
        }
    )
    collected = explore.collect(fetcher)
    assert [n["id"] for n in collected.meta["nodes"]] == ["machine-learning"]
    assert set(collected.members) == {"apache/spark", "tensorflow/tensorflow", "pytorch/pytorch"}


def test_collect_explore_errors():
    url = "https://api.github.com/repos/github/explore/git/trees/main?recursive=1"
    with pytest.raises(SourceError, match="截断"):
        explore.collect(mock_fetcher({url: tree("collections/a/index.md", truncated=True)}))
    with pytest.raises(SourceError, match="没有找到"):
        explore.collect(mock_fetcher({url: tree("README.md")}))
    with pytest.raises(SourceError, match="一个项目都没"):
        explore.collect(
            mock_fetcher(
                {
                    url: tree("collections/videos/index.md"),
                    "https://raw.githubusercontent.com/github/explore/main/collections/videos/index.md": EXPLORE_EMPTY,
                }
            )
        )


# ---- ossinsight ----


def test_file_slug():
    assert ossinsight.file_slug("configs/collections/10004.web-framework.yml") == (
        10004,
        "web-framework",
    )
    assert ossinsight.file_slug("configs/collections/1.static-site-generator.yml") == (
        1,
        "static-site-generator",
    )
    assert ossinsight.file_slug("configs/collections/plain.yaml") == (0, "plain")


def test_parse_ossinsight():
    collected = ossinsight.parse_ossinsight(
        {
            "configs/collections/10004.web-framework.yml": OSS_WEB,
            "configs/collections/1.static-site-generator.yml": OSS_SSG,
            "configs/collections/3.nothing.yml": OSS_EMPTY,
            "configs/collections/4.broken.yml": "id: [unclosed",
        }
    )
    assert [(n["id"], n["label"]) for n in collected.meta["nodes"]] == [
        ("static-site-generator", "Static Site Generator"),  # 数字前缀小的排前面
        ("web-framework", "Web Framework"),
    ]
    assert collected.members["rails/rails"] == ["static-site-generator", "web-framework"]
    assert collected.meta["primary"] is False and collected.meta["order"] == 20
    assert collected.meta["source"]["license"] == "Apache-2.0"
    assert all("guidance" not in n for n in collected.meta["nodes"])
    assert_meta_valid(collected)


def test_collect_ossinsight():
    base = "https://raw.githubusercontent.com/pingcap/ossinsight/main/configs/collections/"
    fetcher = mock_fetcher(
        {
            "https://api.github.com/repos/pingcap/ossinsight/git/trees/main?recursive=1": tree(
                "configs/collections/10004.web-framework.yml",
                "configs/collections/1.static-site-generator.yml",
                "configs/queries/x.yml",
            ),
            base + "10004.web-framework.yml": OSS_WEB,
            base + "1.static-site-generator.yml": OSS_SSG,
        }
    )
    collected = ossinsight.collect(fetcher)
    assert len(collected.meta["nodes"]) == 2 and len(collected.members) == 3


# ---- landscape ----


def test_parse_landscape():
    meta = landscape.cncf_meta()
    collected = landscape.parse_landscape(LANDSCAPE, meta)
    assert [(n["id"], n["parent"]) for n in collected.meta["nodes"]] == [
        ("provisioning", None),
        ("provisioning.automation-configuration", "provisioning"),
        ("provisioning.security-compliance", "provisioning"),
        ("runtime", None),
        ("runtime.empty-one", "runtime"),
        ("runtime.container-runtime", "runtime"),
    ]
    assert collected.meta["nodes"][1]["label"] == "Automation & Configuration"
    assert collected.members == {
        # 同一项目出现在多个子类别：按出现顺序保留，第一个是主分类
        "ansible/ansible": [
            "provisioning.automation-configuration",
            "provisioning.security-compliance",
        ],
        "ansible/ansible-lint": ["provisioning.automation-configuration"],
        "containerd/containerd": ["runtime.container-runtime"],
    }
    assert_meta_valid(collected)


def test_parse_landscape_rejects_bad_structure():
    with pytest.raises(SourceError, match="landscape 列表"):
        landscape.parse_landscape("foo: 1", {})
    with pytest.raises(SourceError, match="YAML"):
        landscape.parse_landscape("landscape: [unclosed", {})


def test_collect_cncf_and_lfai_share_parser():
    fetcher = mock_fetcher({landscape.CNCF_URL: LANDSCAPE, landscape.LFAI_URL: LANDSCAPE})
    cncf, lfai = landscape.collect_cncf(fetcher), landscape.collect_lfai(fetcher)
    assert cncf.members == lfai.members
    assert (cncf.meta["order"], lfai.meta["order"]) == (40, 50)
    assert cncf.meta["primary"] is True and lfai.meta["primary"] is True
    assert cncf.meta["source"]["url"] != lfai.meta["source"]["url"]
    assert {cncf.meta["source"]["license"], lfai.meta["source"]["license"]} == {"Apache-2.0"}
    assert_meta_valid(cncf)
    assert_meta_valid(lfai)


def test_collect_landscape_without_github_projects():
    text = "landscape:\n  - category:\n    name: A\n    subcategories:\n      - subcategory:\n        name: B\n"
    with pytest.raises(SourceError, match="GitHub 项目"):
        landscape.collect_cncf(mock_fetcher({landscape.CNCF_URL: text}))


# ---- 登记与同步 ----


def test_registry_has_all_sources():
    assert list(registry()) == ["explore", "ossinsight", "borges", "cncf", "lfai"]


def test_sync_apply_borges_end_to_end():
    collected = borges.parse_borges(BORGES_CSV)
    names = ["twbs/bootstrap", "git/git", "other/repo"]
    # torvalds/linux 在总榜里改名过，按 aliases 对上；不在总榜的项目被丢弃
    meta, rows = sync.apply(
        collected,
        names + ["torvalds/linux2"],
        {"torvalds/linux2": ["torvalds/linux"]},
        date(2026, 5, 1),
    )
    assert meta["as_of"] == "2026-05-01"
    by_name = {r["full_name"]: r for r in rows}
    assert set(by_name) == {"twbs/bootstrap", "git/git", "torvalds/linux2"}
    assert by_name["git/git"]["category"] == "software-tools"
    assert by_name["git/git"]["related"] == []
    # 没有用到的领域节点被裁掉
    assert {n["id"] for n in meta["nodes"]} == {
        "web-libraries-and-frameworks",
        "system-software",
        "software-tools",
    }
    json.dumps(meta)


def test_sync_apply_landscape_keeps_parents_and_related():
    collected = landscape.parse_landscape(LANDSCAPE, landscape.cncf_meta())
    meta, rows = sync.apply(collected, ["ansible/ansible"], {}, date(2026, 5, 1))
    (row,) = rows
    assert row["category"] == "provisioning.automation-configuration"
    assert row["related"] == ["provisioning.security-compliance"]
    assert [n["id"] for n in meta["nodes"]] == [
        "provisioning",
        "provisioning.automation-configuration",
        "provisioning.security-compliance",
    ]


def test_sync_apply_without_any_match():
    collected = borges.parse_borges(BORGES_CSV)
    with pytest.raises(SourceError, match="对得上"):
        sync.apply(collected, ["nobody/home"], {}, date(2026, 5, 1))
