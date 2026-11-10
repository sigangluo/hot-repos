"""来源 cncf、lfai：Linux Foundation 系的 Landscape（cncf/landscape、lfai/lfai-landscape）。

两个仓库的 `landscape.yml` 格式相同：`landscape` 下是类别，类别下是子类别，子类别下是项目，
写法比较特殊（`category:`、`subcategory:`、`item:` 的值为空，名字在同级的 `name:` 里）。
体系是两级树：类别（一级）与子类别（`类别.子类别`）；项目挂在子类别上，一个项目出现在多个子类别时
按出现顺序全部保留，第一个为主分类。只取项目的 `repo_url` 与 `additional_repos`；没有 GitHub 仓库的条目
（成员公司、产品等）直接略过。

许可：两个仓库的 README 声明，除 Crunchbase 数据与 logo 外均为 Apache-2.0，`landscape.yml`
另以 CC-BY-4.0 提供。本站只用其中的分类结构与仓库地址，不涉及 Crunchbase 数据与 logo。
"""

import logging
from typing import Any

import yaml

from . import Collected, Fetcher, SourceError, dated
from .explore import load_yaml, repo_name, slugify, unique_label, unique_slug

log = logging.getLogger(__name__)

CNCF_URL = "https://raw.githubusercontent.com/cncf/landscape/master/landscape.yml"
LFAI_URL = "https://raw.githubusercontent.com/lfai/lfai-landscape/main/landscape.yml"


def _entries(value: object) -> list[dict[str, Any]]:
    """YAML 里列表可能为空（None）或混入非映射的元素，统一成映射列表。"""
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def _name(entry: dict[str, Any]) -> str | None:
    name = entry.get("name")
    return str(name).strip() if name is not None and str(name).strip() else None


def item_repos(item: dict[str, Any]) -> list[str]:
    """一个项目涉及的 GitHub 仓库：repo_url 在前，additional_repos 在后，已去重。"""
    urls = [item.get("repo_url")] + [
        a.get("repo_url") for a in _entries(item.get("additional_repos"))
    ]
    return list(dict.fromkeys(r for r in map(repo_name, urls) if r))


def parse_landscape(text: str, meta: dict[str, Any]) -> Collected:
    """解析 landscape.yml；meta 是体系定义里除 nodes 以外的字段。"""
    try:
        data = load_yaml(text)
    except yaml.YAMLError as e:
        raise SourceError(f"landscape.yml 不是合法的 YAML：{e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("landscape"), list):
        raise SourceError("landscape.yml 里没有 landscape 列表（文件格式可能变了）")
    nodes: list[dict[str, Any]] = []
    members: dict[str, list[str]] = {}
    top_ids: set[str] = set()
    top_labels: set[str] = set()
    for category in _entries(data["landscape"]):
        cat_name = _name(category)
        if cat_name is None:
            continue
        cat_id = unique_slug(slugify(cat_name), top_ids)
        nodes.append(
            {"id": cat_id, "label": unique_label(cat_name, cat_id, top_labels), "parent": None}
        )
        sub_ids: set[str] = set()
        sub_labels: set[str] = set()
        for sub in _entries(category.get("subcategories")):
            sub_name = _name(sub)
            if sub_name is None:
                continue
            sub_slug = unique_slug(slugify(sub_name), sub_ids)
            sub_id = f"{cat_id}.{sub_slug}"
            nodes.append(
                {
                    "id": sub_id,
                    "label": unique_label(sub_name, sub_slug, sub_labels),
                    "parent": cat_id,
                }
            )
            for item in _entries(sub.get("items")):
                for repo in item_repos(item):
                    ids = members.setdefault(repo, [])
                    if sub_id not in ids:
                        ids.append(sub_id)
    return Collected(meta=meta | {"nodes": nodes}, members=members)


def _collect(fetcher: Fetcher, url: str, meta: dict[str, Any], label: str, repo: str) -> Collected:
    collected = dated(
        parse_landscape(fetcher.text(url), meta), *fetcher.github_dates(repo, "landscape.yml")
    )
    if not collected.members:
        raise SourceError(f"{label} 里没有解析出任何 GitHub 项目（文件格式可能变了）")
    log.info(
        "%s：%d 个节点，%d 个项目", label, len(collected.meta["nodes"]), len(collected.members)
    )
    return collected


def cncf_meta() -> dict[str, Any]:
    return {
        "name": "CNCF Cloud Native Landscape",
        "summary": "云原生计算基金会（CNCF）维护的云原生全景图，由社区提交、CNCF 审核，把云原生项目归入“类别 / 子类别”。",
        "method": "curated",
        "order": 40,
        "primary": True,
        "note": "只收录在全景图里登记了 GitHub 仓库的项目，侧重云原生与基础设施，对总榜的覆盖面有限。一个项目可能出现在多个子类别：第一个作为主分类，其余作为关联分类；类别和子类别的名称保持英文原样。",
        "source": {
            "name": "CNCF Cloud Native Landscape（cncf/landscape）",
            "url": "https://github.com/cncf/landscape",
            "license": "Apache-2.0",
            "attribution": "Cloud Native Computing Foundation (CNCF) 及 landscape 贡献者，cncf/landscape 的 landscape.yml（Apache-2.0，该文件另以 CC-BY-4.0 提供）。不含其中的 Crunchbase 数据与 logo。",
        },
    }


def lfai_meta() -> dict[str, Any]:
    return {
        "name": "LF AI & Data Landscape",
        "summary": "Linux Foundation 旗下 LF AI & Data 基金会维护的人工智能与数据领域全景图，把相关开源项目归入“类别 / 子类别”。",
        "method": "curated",
        "order": 50,
        "primary": True,
        "note": "只收录在全景图里登记了 GitHub 仓库的项目，侧重 AI 与数据领域的开源基础设施，对总榜的覆盖面有限。一个项目可能出现在多个子类别：第一个作为主分类，其余作为关联分类；类别和子类别的名称保持英文原样。",
        "source": {
            "name": "LF AI & Data Landscape（lfai/lfai-landscape）",
            "url": "https://github.com/lfai/lfai-landscape",
            "license": "Apache-2.0",
            "attribution": "LF AI & Data Foundation 及 landscape 贡献者，lfai/lfai-landscape 的 landscape.yml（Apache-2.0，该文件另以 CC-BY-4.0 提供）。不含其中的 Crunchbase 数据与 logo。",
        },
    }


def collect_cncf(fetcher: Fetcher) -> Collected:
    return _collect(fetcher, CNCF_URL, cncf_meta(), "cncf", "cncf/landscape")


def collect_lfai(fetcher: Fetcher) -> Collected:
    return _collect(fetcher, LFAI_URL, lfai_meta(), "lfai", "lfai/lfai-landscape")
