"""来源 wikidata：Wikidata（维基数据）给软件项目标注的类型。

Wikidata 里有很多软件条目带着“源代码仓库”（P1324）指向 GitHub，并用“instance of”（P31）标注它是
什么类型的东西（Python 包、自由软件、JavaScript 库、文本编辑器……）。这是知识库社区编辑出来的分类，
不是互斥的：一个条目可以有多个类型。体系是一级、没有主分类，每个类型一个节点，名称取英文标签。

数据通过 Wikidata Query Service（SPARQL）一次取回，三个请求：全部（仓库，类型）对、类型的英文标签、
这批条目最近一次被编辑的时间。Wikidata 的结构化数据以 CC0 发布，不需要署名，仍然注明出处。
"""

import csv
import io
import logging
from typing import Any
from urllib.parse import quote

from . import Collected, Fetcher, SourceError, dated
from .explore import repo_name, slugify, unique_label, unique_slug

log = logging.getLogger(__name__)

ENDPOINT = "https://query.wikidata.org/sparql"
CSV = {"Accept": "text/csv"}
WIKIDATA_LAUNCH = "2012-10-29"  # Wikidata 上线的日期，作为这个体系的创建日期

_ITEMS = (
    "?item wdt:P1324 ?repo . ?item wdt:P31 ?class . "
    'FILTER(STRSTARTS(STR(?repo), "https://github.com/"))'
)
PAIRS_QUERY = f"SELECT ?repo ?class WHERE {{ {_ITEMS} }}"
LABELS_QUERY = (
    f"SELECT DISTINCT ?class ?classLabel WHERE {{ {_ITEMS} "
    'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'
)
UPDATED_QUERY = f"SELECT (MAX(?modified) AS ?updated) WHERE {{ {_ITEMS} ?item schema:dateModified ?modified . }}"


def _qid(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def parse_wikidata(pairs_csv: str, labels_csv: str) -> Collected:
    """pairs_csv：列 repo、class（URI）；labels_csv：列 class、classLabel。没有英文标签的类型略过。"""
    labels: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(labels_csv)):
        qid, label = _qid(row.get("class") or ""), (row.get("classLabel") or "").strip()
        if qid and label and label != qid:  # 没有标签时服务返回编号本身
            labels[qid] = label
    pairs: dict[str, list[str]] = {}
    for row in csv.DictReader(io.StringIO(pairs_csv)):
        repo, qid = repo_name(row.get("repo")), _qid(row.get("class") or "")
        if repo and qid in labels and qid not in pairs.setdefault(repo, []):
            pairs[repo].append(qid)
    used = sorted({q for qs in pairs.values() for q in qs}, key=lambda q: (labels[q].casefold(), q))
    ids: set[str] = set()
    names: set[str] = set()
    node_of: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    for qid in used:
        node_id = unique_slug(slugify(qid), ids)
        node_of[qid] = node_id
        nodes.append(
            {
                "id": node_id,
                "label": unique_label(labels[qid], qid, names),
                "parent": None,
                "guidance": {"includes": f"Wikidata 类别 {qid}（条目的 instance of 取值）。"},
            }
        )
    members = {repo: [node_of[q] for q in qids] for repo, qids in pairs.items() if qids}
    meta = {
        "name": "Wikidata 软件类型",
        "summary": "Wikidata（维基数据）里给软件项目标注的类型（instance of）：知识库的社区编辑者把带 GitHub 仓库的软件条目归入“Python 包”“自由软件”“JavaScript 库”等类别。",
        "method": "curated",
        "order": 25,
        "primary": False,
        "note": "Wikidata 只收录有条目的软件（多为较知名的项目），一个条目可以有多个类型，没有主分类。类型名称取英文标签，粗细不一（如“自由软件”“软件”很宽泛），部分条目由机器人批量导入，可能不完整。",
        "source": {
            "name": "Wikidata（P1324 源代码仓库 + P31 instance of）",
            "url": "https://www.wikidata.org/",
            "license": "CC0-1.0",
            "attribution": "Wikidata 贡献者；Wikidata 的结构化数据以 CC0 发布，通过 Wikidata Query Service 取得。",
        },
        "nodes": nodes,
    }
    return Collected(meta=meta, members=members)


def _query(fetcher: Fetcher, query: str) -> str:
    return fetcher.text(f"{ENDPOINT}?query={quote(query)}", CSV)


def collect(fetcher: Fetcher) -> Collected:
    collected = parse_wikidata(_query(fetcher, PAIRS_QUERY), _query(fetcher, LABELS_QUERY))
    if not collected.members:
        raise SourceError("Wikidata 没有返回任何带 GitHub 仓库的软件条目（接口或数据模型可能变了）")
    rows = list(csv.DictReader(io.StringIO(_query(fetcher, UPDATED_QUERY))))
    updated = (rows[0].get("updated") or "")[:10] if rows else ""
    if not updated:
        raise SourceError("取不到 Wikidata 条目的最近编辑时间")
    log.info("wikidata：%d 个类型，%d 个项目", len(collected.meta["nodes"]), len(collected.members))
    return dated(collected, WIKIDATA_LAUNCH, updated)
