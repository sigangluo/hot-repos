"""来源 borges：Borges 与 Valente 对 5000 个热门 GitHub 项目“应用领域”的人工分类（Zenodo 804474）。

数据集由研究者手工标注，把 2017 年 1 月 Star 最多的 5000 个项目各归入六个领域之一（单一归属），
以 CC-BY-4.0 发布。CSV 列：Name（`owner/repo`）、Stars、Forks、Language、Description、URL、Domain、
Growth Pattern；这里只取 Name 和 Domain。
"""

import csv
import io
import logging
from typing import Any

from . import Collected, Fetcher, SourceError

log = logging.getLogger(__name__)

CSV_URL = (
    "https://zenodo.org/api/records/804474/files/"
    "Domains%20of%205,000%20GitHub%20Repositories%20-%20Public%20-%20Domains.csv/content"
)

# 六个领域按数据集页面的顺序；说明由本站依据页面上的英文定义译写，示例项目也出自该页面。
DOMAINS: list[tuple[str, str, str]] = [
    (
        "application-software",
        "Application software",
        "面向最终用户提供功能的系统，例如浏览器、文本编辑器（数据集示例：WordPress/WordPress、adobe/brackets）。",
    ),
    (
        "system-software",
        "System software",
        "为其他系统提供服务和基础设施的系统，例如操作系统、中间件、数据库（数据集示例：torvalds/linux、mongodb/mongo）。",
    ),
    (
        "web-libraries-and-frameworks",
        "Web libraries and frameworks",
        "用于 Web 开发的库和框架（数据集示例：twbs/bootstrap、angular/angular.js）。",
    ),
    (
        "non-web-libraries-and-frameworks",
        "Non-web libraries and frameworks",
        "用于 Web 以外场景的库和框架（数据集示例：google/guava、facebook/fresco）。",
    ),
    (
        "software-tools",
        "Software tools",
        "支持开发工作的系统，例如 IDE、包管理器、编译器（数据集示例：Homebrew/homebrew、git/git）。",
    ),
    (
        "documentation",
        "Documentation",
        "以文档、教程、源代码示例等为主的仓库（数据集示例：iluwatar/java-design-patterns）。",
    ),
]


def parse_borges(text: str) -> Collected:
    """解析 CSV。Name 或 Domain 为空、Domain 不在六个领域内的行会被略过并记录。"""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or not {"Name", "Domain"} <= set(reader.fieldnames):
        raise SourceError(f"Borges 数据集的列不是预期的格式：{reader.fieldnames}")
    by_label = {label: node_id for node_id, label, _ in DOMAINS}
    members: dict[str, list[str]] = {}
    skipped: list[str] = []
    for row in reader:
        name = (row["Name"] or "").strip()
        node_id = by_label.get((row["Domain"] or "").strip())
        if name.count("/") != 1 or node_id is None:
            skipped.append(f"{name or '(空)'}：{row['Domain']!r}")
            continue
        members[name] = [node_id]
    if skipped:
        log.warning("borges：%d 行的项目名或领域不合规，已略过：%s", len(skipped), skipped[:5])
    nodes: list[dict[str, Any]] = [
        {"id": node_id, "label": label, "parent": None, "guidance": {"includes": guidance}}
        for node_id, label, guidance in DOMAINS
    ]
    meta = {
        "name": "Borges 等的人工分类（2017）",
        "summary": "巴西米纳斯吉拉斯联邦大学的 Borges 与 Valente 由研究者逐个人工标注，把 2017 年 1 月 Star 最多的 5000 个项目各归入六个应用领域之一。",
        "method": "manual",
        "order": 30,
        "primary": True,
        "note": "这是 2017 年 1 月当时 Star 前 5000 的项目快照，所以只覆盖当年已经很热门、且至今仍用同一名称的项目（改名的按总榜记录的旧名尽量对上），近年的项目基本不在其中。六个应用领域划分较粗，每个项目只属于一个领域；领域说明由本站依据数据集页面的英文定义译写。",
        "source": {
            "name": "Application Domain of 5,000 GitHub Repositories（Zenodo）",
            "url": "https://doi.org/10.5281/zenodo.804474",
            "license": "CC-BY-4.0",
            "attribution": (
                "Hudson Borges, Marco Tulio Valente. Application Domain of 5,000 GitHub Repositories."
                " Zenodo, 2017. doi:10.5281/zenodo.804474."
                " 数据集作者建议同时引用：Hudson Borges, Andre Hora, Marco Tulio Valente."
                " Understanding the Factors that Impact the Popularity of GitHub Repositories."
                " ICSME 2016, pp. 334-344."
            ),
        },
        "nodes": nodes,
    }
    return Collected(meta=meta, members=members)


def collect(fetcher: Fetcher) -> Collected:
    collected = parse_borges(fetcher.text(CSV_URL))
    if not collected.members:
        raise SourceError("Borges 数据集里一行有效数据都没有（文件格式可能变了）")
    log.info("borges：%d 个项目", len(collected.members))
    return collected
