"""来源 ossinsight：OSS Insight 的开源项目合集（pingcap/ossinsight 仓库的 configs/collections/）。

每个合集一个 YAML：`id`、`name`、`items`（`owner/repo` 列表）。不直接用 api.ossinsight.io
（经常返回 500），读的是接口背后的同一份配置文件。一个项目可属于多个合集，所以体系没有主分类。
仓库以 Apache-2.0 发布，配置文件在许可范围内。
"""

import logging
import re
from typing import Any

import yaml

from . import Collected, Fetcher, SourceError, dated
from .explore import list_files, load_yaml, raw_url, repo_name, slugify, unique_label, unique_slug

log = logging.getLogger(__name__)

REPO = "pingcap/ossinsight"
BRANCH = "main"
COLLECTION_PATH = re.compile(r"configs/collections/[^/]+\.ya?ml")
_PREFIX = re.compile(r"^(\d+)\.")


def file_slug(path: str) -> tuple[int, str]:
    """`configs/collections/10004.web-framework.yml` -> (10004, "web-framework")；没有数字前缀时序号取 0。"""
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    m = _PREFIX.match(stem)
    return (int(m[1]) if m else 0, stem[m.end() :] if m else stem)


def parse_ossinsight(files: dict[str, str]) -> Collected:
    """files：{文件路径: yml 全文}。节点按文件名里的数字前缀排序；没有项目的合集、解析不了的文件会被略过。"""
    nodes: list[dict[str, Any]] = []
    members: dict[str, list[str]] = {}
    used_ids: set[str] = set()
    used_labels: set[str] = set()
    for path in sorted(files, key=file_slug):
        try:
            data = load_yaml(files[path])
        except yaml.YAMLError:
            data = None
        if not isinstance(data, dict):
            log.warning("ossinsight：%s 不是合法的 YAML 映射，已略过", path)
            continue
        items = data.get("items")
        repos = list(
            dict.fromkeys(r for r in map(repo_name, items if isinstance(items, list) else []) if r)
        )
        if not repos:
            continue
        slug = file_slug(path)[1]
        node_id = unique_slug(slugify(slug), used_ids)
        name = data.get("name")
        label = unique_label(
            str(name).strip() if name is not None and str(name).strip() else slug,
            node_id,
            used_labels,
        )
        nodes.append({"id": node_id, "label": label, "parent": None})
        for repo in repos:
            members.setdefault(repo, []).append(node_id)
    meta = {
        "name": "OSS Insight 开源项目合集",
        "summary": "PingCAP 的 OSS Insight 项目由社区维护的开源项目合集（如 Web 框架、静态站点生成器、开源数据库），把同一类开源项目收在一起。",
        "method": "curated",
        "order": 20,
        "primary": False,
        "note": "合集是 OSS Insight 为榜单统计整理的项目清单，不是互斥分类，一个项目可以同时属于多个合集；每个合集只收录该领域有代表性的项目，覆盖面有限。",
        "source": {
            "name": "OSS Insight Collections（pingcap/ossinsight）",
            "url": "https://github.com/pingcap/ossinsight",
            "license": "Apache-2.0",
            "attribution": "PingCAP 及 OSS Insight 贡献者，pingcap/ossinsight 仓库 configs/collections 中的合集配置（Apache-2.0）。",
        },
        "nodes": nodes,
    }
    return Collected(meta=meta, members=members)


def collect(fetcher: Fetcher) -> Collected:
    paths = list_files(fetcher, REPO, BRANCH, COLLECTION_PATH)
    texts = fetcher.texts([raw_url(REPO, BRANCH, p) for p in paths])
    collected = dated(
        parse_ossinsight(dict(zip(paths, texts, strict=True))),
        *fetcher.github_dates(REPO, "configs/collections"),
    )
    if not collected.meta["nodes"]:
        raise SourceError("ossinsight 的合集里一个项目都没解析出来（文件格式可能变了）")
    log.info(
        "ossinsight：%d 个合集，%d 个项目", len(collected.meta["nodes"]), len(collected.members)
    )
    return collected
