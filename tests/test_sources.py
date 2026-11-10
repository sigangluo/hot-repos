"""外部分类来源的解析与取数测试：全部离线，用内联的小样本和 MockTransport。"""

import json
import re
from datetime import date

import httpx
import pytest

from hot_repos import sync
from hot_repos.sources import (
    Fetcher,
    SourceError,
    awesome,
    borges,
    dated,
    explore,
    landscape,
    ossinsight,
    registry,
    wikidata,
)
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
        url = str(request.url)
        body = routes.get(url)
        if body is None and re.fullmatch(r"https://api\.github\.com/repos/[^/]+/[^/?]+", url):
            body = {"created_at": "2020-01-02T03:04:05Z", "pushed_at": "2026-01-03T00:00:00Z"}
        elif body is None and "/commits?path=" in url:
            body = [{"commit": {"committer": {"date": "2026-01-04T05:06:07Z"}}}]  # type: ignore[assignment]
        elif body is None and url == borges.RECORD_URL:
            body = {
                "metadata": {"publication_date": "2017-06-08"},
                "updated": "2020-01-24T19:26:12Z",
            }
        if body is None:
            return httpx.Response(404)
        if isinstance(body, dict | list):
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
    meta = {"created": "2020-01-01", "updated": "2026-01-01"} | collected.meta | {"as_of": as_of}
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
    assert (collected.meta["created"], collected.meta["updated"]) == ("2017-06-08", "2020-01-24")
    assert_meta_valid(collected)


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
    assert (collected.meta["created"], collected.meta["updated"]) == ("2020-01-02", "2026-01-04")
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
    assert (cncf.meta["created"], cncf.meta["updated"]) == ("2020-01-02", "2026-01-04")
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
    assert list(registry()) == [
        "explore",
        "awesome",
        "awesome-site",
        "ossinsight",
        "wikidata",
        "borges",
        "cncf",
        "lfai",
    ]


def test_sync_apply_borges_end_to_end():
    collected = dated(borges.parse_borges(BORGES_CSV), "2017-06-08", "2020-01-24")
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
    collected = dated(
        landscape.parse_landscape(LANDSCAPE, landscape.cncf_meta()), "2020-01-02", "2026-01-04"
    )
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


# ---------- awesome ----------

README = """# Awesome Demo [![Awesome](https://awesome.re/badge.svg)](https://github.com/sindresorhus/awesome)

> 简介里提到 [x/intro](https://github.com/x/intro)，不算收录。

## Contents
- [Web](#web)
- [Data](#data)

## Web

- [a/one](https://github.com/a/one) - 一个
- [b/two](https://github.com/b/two/) - 两个，同一章节重复 [b/two](https://github.com/b/two)
- 自己：[me/awesome-demo](https://github.com/me/awesome-demo)

### Sub heading

- [c/three](https://github.com/c/three.git)

## Data

```
https://github.com/in/code
```

- [d/four](https://github.com/d/four/tree/main/docs)
- [e/five](https://github.com/topics/web)
- [f/six](https://github.com/f/six)

## Contributing

- [z/skipped](https://github.com/z/skipped)
"""


def test_parse_awesome_sections_and_links():
    sections = awesome.parse_awesome(README, "me/awesome-demo")
    assert sections == {"Web": ["a/one", "b/two", "c/three"], "Data": ["d/four", "f/six"]}


def test_parse_awesome_picks_the_level_with_the_categories():
    text = (
        "# Title\n## Projects\n"
        + "".join(
            f"### Cat{i}\n"
            + "".join(f"- [o{i}/r{j}](https://github.com/o{i}/r{j})\n" for j in range(3))
            for i in range(3)
        )
        + "## Contributing\n- [z/y](https://github.com/z/y)\n"
    )
    sections = awesome.parse_awesome(text, "me/list")
    assert list(sections) == ["Cat0", "Cat1", "Cat2"]


def test_parse_awesome_skips_children_of_filtered_sections():
    text = (
        "## Tools\n- [a/a](https://github.com/a/a)\n- [a/b](https://github.com/a/b)\n- [a/c](https://github.com/a/c)\n"
        "## Related\n### Other\n- [z/z](https://github.com/z/z)\n"
        "## Libs\n- [l/a](https://github.com/l/a)\n- [l/b](https://github.com/l/b)\n- [l/c](https://github.com/l/c)\n"
    )
    assert awesome.parse_awesome(text, "me/list") == {
        "Tools": ["a/a", "a/b", "a/c"],
        "Libs": ["l/a", "l/b", "l/c"],
    }


def test_parse_awesome_without_headings_is_one_flat_list():
    text = "[a/a](https://github.com/a/a) [b/b](https://github.com/b/b) https://github.com/c/c"
    assert awesome.parse_awesome(text, "me/list") == {None: ["a/a", "b/b", "c/c"]}


def test_clean_heading():
    assert (
        awesome.clean_heading("🚀 [Web](#web) **Frameworks** ![x](y.svg) :fire:")
        == "🚀 Web Frameworks"
    )


def row(name, rank, **changes):
    return {
        "full_name": name,
        "rank": rank,
        "default_branch": "main",
        "readme_path": "README.md",
        "topics": [],
        "description": "一个清单",
        "license": "CC0-1.0",
    } | changes


def test_is_awesome_list():
    assert awesome.is_awesome_list(row("o/awesome-x", 1))
    assert awesome.is_awesome_list(row("o/free-for-dev", 1, topics=["Awesome-List"]))
    assert not awesome.is_awesome_list(row("o/tool", 1))
    assert not awesome.is_awesome_list(row("o/awesome-x", 1, readme_path=None))


def test_build_keeps_lists_with_enough_board_members():
    readmes = {
        "me/awesome-demo": README,
        "me/awesome-tiny": "## A\n- [a/one](https://github.com/a/one)\n",
    }
    lists = [row("me/awesome-demo", 1), row("me/awesome-tiny", 2)]
    board = {"a/one", "b/two", "c/three", "d/four", "f/six"}
    groups = {"me/awesome-demo": "Programming Languages"}
    collected = awesome.build(lists, readmes, board, groups)
    nodes = [n["id"] for n in collected.meta["nodes"]]
    assert nodes == [
        "programming-languages",
        "programming-languages.me-awesome-demo",
        "programming-languages.me-awesome-demo.web",
        "programming-languages.me-awesome-demo.data",
    ]
    group, listing = collected.meta["nodes"][:2]
    assert group["label"] == "Programming Languages" and group["parent"] is None
    assert listing["label"] == "me/awesome-demo" and listing["parent"] == "programming-languages"
    assert "CC0-1.0" in listing["guidance"]["includes"]
    assert collected.members["a/one"] == ["programming-languages.me-awesome-demo.web"]
    assert collected.members["d/four"] == ["programming-languages.me-awesome-demo.data"]
    assert collected.meta["primary"] is False
    assert_meta_valid(collected)


def test_lists_missing_from_the_index_go_to_the_other_group():
    readmes = {"me/awesome-demo": README}
    board = {"a/one", "b/two", "c/three", "d/four", "f/six"}
    collected = awesome.build(
        [row("me/awesome-demo", 1)], readmes, board, {"x/other-list": "Security"}
    )
    group = collected.meta["nodes"][0]
    assert (group["id"], group["label"]) == ("other", awesome.OTHER_LABEL)
    assert collected.meta["nodes"][1]["id"] == "other.me-awesome-demo"
    assert_meta_valid(collected)


INDEX = """# Awesome [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

## Contents
- [Platforms](#platforms)

## Platforms

### Node.js
- [sindresorhus/awesome-nodejs](https://github.com/sindresorhus/awesome-nodejs) - Node
- [Dup/List](https://github.com/Dup/List)

## Security

- [Dup/list](https://github.com/Dup/list)
- [sbilly/awesome-security](https://github.com/sbilly/awesome-security)

## Related

- [x/related](https://github.com/x/related)
"""


def test_parse_groups_uses_the_top_level_sections_and_first_group_wins():
    assert awesome.parse_groups(INDEX) == {
        "sindresorhus/awesome-nodejs": "Platforms",
        "dup/list": "Platforms",
        "sbilly/awesome-security": "Security",
    }


def test_collect_needs_the_index_to_have_groups():
    def handler(request):
        return httpx.Response(
            200, text="# Awesome\n" if "sindresorhus" in str(request.url) else README
        )

    fetcher = Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    board = [row("me/awesome-demo", 1), row("a/one", 2), row("b/two", 3), row("c/three", 4)]
    with pytest.raises(SourceError, match="领域分组"):
        awesome.collect(fetcher, board)


def test_collect_fetches_readmes_from_the_board_rows():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if "bad" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, text=README)

    fetcher = Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    board = [
        row("me/awesome-demo", 1),
        row("a/one", 2, readme_path=None),
        row("b/two", 3),
        row("c/three", 4),
        row("d/four", 5),
    ]
    collected = awesome.collect(fetcher, board)
    assert sorted(seen) == [
        "https://raw.githubusercontent.com/me/awesome-demo/main/README.md",
        awesome.INDEX_URL,
    ]
    # 这里总索引的内容也是 README：它的“Web”章节里提到了 me/awesome-demo，所以清单归入“Web”组
    assert collected.members["a/one"] == ["web.me-awesome-demo.web"]


def test_collect_tolerates_a_few_failures_but_not_many():
    def handler(request):
        return httpx.Response(404 if "bad" in str(request.url) else 200, text=README)

    fetcher = Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    board = [row(f"me/awesome-{i}", i) for i in range(1, 7)] + [
        row("a/one", 7),
        row("b/two", 8),
        row("c/three", 9),
    ]
    assert awesome.collect(fetcher, board).meta["nodes"]  # 6 个清单都取到
    many_bad = board[:2] + [row("me/awesome-bad1", 10), row("me/awesome-bad2", 11)] + board[6:]
    with pytest.raises(SourceError, match="取不到 README"):
        awesome.collect(fetcher, many_bad)


def test_collect_without_any_list():
    with pytest.raises(SourceError, match="没有找到 Awesome 清单"):
        awesome.collect(Fetcher(), [row("o/tool", 1)])


# ---------- wikidata ----------

WD_PAIRS = """repo,class
https://github.com/yaml/pyyaml,http://www.wikidata.org/entity/Q29642950
https://github.com/yaml/pyyaml,http://www.wikidata.org/entity/Q341
https://github.com/torvalds/linux/,http://www.wikidata.org/entity/Q341
https://github.com/a/b,http://www.wikidata.org/entity/Q999
https://gitlab.com/x/y,http://www.wikidata.org/entity/Q341
"""
WD_LABELS = """class,classLabel
http://www.wikidata.org/entity/Q29642950,Python package
http://www.wikidata.org/entity/Q341,free software
http://www.wikidata.org/entity/Q999,Q999
"""


def test_parse_wikidata():
    collected = wikidata.parse_wikidata(WD_PAIRS, WD_LABELS)
    assert [(n["id"], n["label"]) for n in collected.meta["nodes"]] == [
        ("q341", "free software"),
        ("q29642950", "Python package"),
    ]
    # 没有英文标签的类型（Q999）和不是 GitHub 的仓库被略过
    assert collected.members == {
        "yaml/pyyaml": ["q29642950", "q341"],
        "torvalds/linux": ["q341"],
    }
    assert collected.meta["primary"] is False
    assert collected.meta["source"]["license"] == "CC0-1.0"
    assert_meta_valid(collected)


def test_collect_wikidata_queries_and_dates():
    seen = []

    def handler(request):
        seen.append((request.url.params["query"][:30], request.headers["accept"]))
        query = request.url.params["query"]
        if "MAX(" in query:
            return httpx.Response(200, text="updated\n2026-11-09T12:00:00Z\n")
        return httpx.Response(200, text=WD_LABELS if "classLabel" in query else WD_PAIRS)

    fetcher = Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    collected = wikidata.collect(fetcher)
    assert (collected.meta["created"], collected.meta["updated"]) == ("2012-10-29", "2026-11-09")
    assert len(seen) == 3 and {accept for _, accept in seen} == {"text/csv"}
    assert_meta_valid(collected)


def test_collect_wikidata_without_data():
    fetcher = mock_fetcher({})
    with pytest.raises(SourceError):
        wikidata.collect(fetcher)


# ---------- 创建与更新日期 ----------


def test_github_dates():
    fetcher = mock_fetcher(
        {
            "https://api.github.com/repos/o/r": {
                "created_at": "2019-03-04T00:00:00Z",
                "pushed_at": "2026-02-03T00:00:00Z",
            },
            "https://api.github.com/repos/o/r/commits?path=a/b.yml&per_page=1": [
                {"commit": {"committer": {"date": "2025-12-31T23:59:59Z"}}}
            ],
        }
    )
    assert fetcher.github_dates("o/r") == ("2019-03-04", "2026-02-03")
    assert fetcher.github_dates("o/r", "a/b.yml") == ("2019-03-04", "2025-12-31")


def test_github_dates_with_unexpected_responses():
    fetcher = mock_fetcher(
        {
            "https://api.github.com/repos/o/r": {"created_at": "2019-03-04T00:00:00Z"},
            "https://api.github.com/repos/o/r/commits?path=x&per_page=1": [],
        }
    )
    with pytest.raises(SourceError, match="创建与更新日期"):
        fetcher.github_dates("o/r")
    with pytest.raises(SourceError, match="创建与更新日期"):
        fetcher.github_dates("o/r", "x")


def test_awesome_scheme_dates_come_from_the_list_repos():
    from datetime import UTC, datetime

    readmes = {"me/awesome-demo": README}
    lists = [
        row(
            "me/awesome-demo",
            1,
            created_at=datetime(2018, 5, 6, tzinfo=UTC),
            pushed_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
    ]
    board = {"a/one", "b/two", "c/three", "d/four", "f/six"}
    collected = awesome.build(lists, readmes, board)
    assert (collected.meta["created"], collected.meta["updated"]) == ("2018-05-06", "2026-10-01")
    listing = next(n for n in collected.meta["nodes"] if n["id"] == "other.me-awesome-demo")
    guidance = listing["guidance"]["includes"]
    assert "创建于 2018-05-06" in guidance and "最近推送 2026-10-01" in guidance
    assert_meta_valid(collected)


# ---------- awesome：本站分组 ----------

VOCAB = {
    "web": {"label": "网页开发", "definition": "网页相关的清单。"},
    "other-stuff": {"label": "别的", "definition": "别的清单。"},
}


def test_build_site_groups_by_the_site_vocabulary():
    readmes = {"me/awesome-demo": README}
    board = {"a/one", "b/two", "c/three", "d/four", "f/six"}
    collected = awesome.build_site(
        [row("me/awesome-demo", 1)], readmes, board, VOCAB, {"Me/Awesome-Demo": "web"}
    )
    assert [n["id"] for n in collected.meta["nodes"]] == [
        "web",
        "web.me-awesome-demo",
        "web.me-awesome-demo.web",
        "web.me-awesome-demo.data",
    ]
    group = collected.meta["nodes"][0]
    assert (
        group["label"] == "网页开发"
        and group["guidance"]["includes"] == "本站定义：网页相关的清单。"
    )
    assert collected.meta["method"] == "model" and collected.meta["name"].endswith("本站分组")
    assert collected.meta["order"] == 16 and collected.meta["primary"] is False
    assert collected.members["a/one"] == ["web.me-awesome-demo.web"]
    assert_meta_valid(collected)


def test_build_site_puts_unmapped_lists_in_the_other_group():
    readmes = {"me/awesome-demo": README}
    board = {"a/one", "b/two", "c/three", "d/four", "f/six"}
    collected = awesome.build_site(
        [row("me/awesome-demo", 1)], readmes, board, VOCAB, {"me/awesome-demo": "gone"}
    )
    group = collected.meta["nodes"][0]
    assert (group["id"], group["label"]) == ("other", awesome.SITE_OTHER_LABEL)
    assert_meta_valid(collected)


def test_the_two_awesome_views_share_lists_and_sections_but_not_groups():
    readmes = {"me/awesome-demo": README}
    board = {"a/one", "b/two", "c/three", "d/four", "f/six"}
    lists = [row("me/awesome-demo", 1)]
    other = awesome.build(lists, readmes, board, {"me/awesome-demo": "Security"})
    site = awesome.build_site(lists, readmes, board, VOCAB, {"me/awesome-demo": "web"})
    tail = lambda c: [n["id"].split(".", 1)[1] for n in c.meta["nodes"] if "." in n["id"]]  # noqa: E731
    assert tail(other) == tail(site)
    assert other.meta["nodes"][0]["label"] != site.meta["nodes"][0]["label"]


def test_the_groups_file_is_consistent():
    mapping = awesome.load_groups()
    vocabulary = mapping["vocabulary"]
    assert all(v["label"].strip() and v["definition"].strip() for v in vocabulary.values())
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", key) for key in vocabulary)
    assert len({v["label"] for v in vocabulary.values()}) == len(vocabulary)
    assert set(mapping["groups"].values()) <= set(vocabulary)
    assert not {n.lower() for n in mapping["groups"]} & {n.lower() for n in mapping["exclude"]}


def test_candidate_lists_drop_excluded_repositories():
    rows = [row("me/awesome-demo", 2), row("lissy93/dashy", 1, topics=["awesome"])]
    assert [r["full_name"] for r in awesome.candidate_lists(rows)] == ["me/awesome-demo"]


def test_collect_site_does_not_need_the_index():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=README)

    fetcher = Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    board = [
        row("me/awesome-demo", 1),
        row("a/one", 2, readme_path=None),
        row("b/two", 3),
        row("c/three", 4),
        row("d/four", 5),
    ]
    collected = awesome.collect_site(fetcher, board)
    assert awesome.INDEX_URL not in seen
    assert collected.meta["nodes"][0]["id"] == "other"  # 映射文件里没有 me/awesome-demo


def test_fetcher_reuses_text_within_a_run():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text="x")

    fetcher = Fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    assert [fetcher.text("https://example.com/a") for _ in range(3)] == ["x", "x", "x"]
    fetcher.text("https://example.com/a", {"Accept": "text/csv"})  # 请求头不同，另取
    assert len(calls) == 2
