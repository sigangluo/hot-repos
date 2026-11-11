"""分类体系：`data/schemes/<编号>/` 下的体系定义（scheme.json）与各项目的标注（labels.parquet）。

一个体系回答“这些项目分别属于什么类”。体系直接来自别人已经做好的分类（Borges 等的人工标注、
CNCF Landscape 等，见 `sources/`），只保存“哪个项目属于来源里的哪个类”这个事实，并注明出处与许可，
不重新标注。

两个文件都是可选数据，体系定义可以先于标注存在。采集总榜（`fetch`）不生成它们，只负责让标注里的
项目名和总榜保持一致（见 `reconcile`、`carry`）。结构见 docs/data-model.md。
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from . import cache, config, schema

log = logging.getLogger(__name__)

# 标注方式：体系里的分类是谁、怎么定的。页面据此提示可信度。
METHODS = {
    "model": "语言模型判断",
    "manual": "研究者人工标注",
    "curated": "来源方人工策展",
}
DEFAULT_ORDER = 100
ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def scheme_dir(data_dir: Path, scheme_id: str) -> Path:
    return data_dir / config.SCHEMES_DIR_NAME / scheme_id


def read_meta(data_dir: Path, scheme_id: str) -> dict[str, Any] | None:
    path = scheme_dir(data_dir, scheme_id) / config.SCHEME_META_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_meta(data_dir: Path, scheme_id: str, meta: dict[str, Any]) -> None:
    cache.write_json(scheme_dir(data_dir, scheme_id) / config.SCHEME_META_FILE, meta, indent=1)


def read_rows(data_dir: Path, scheme_id: str) -> list[dict[str, Any]]:
    """读取标注；文件不存在时返回空列表。"""
    path = scheme_dir(data_dir, scheme_id) / config.SCHEME_LABELS_FILE
    return pq.read_table(path).to_pylist() if path.exists() else []


def write_rows(data_dir: Path, scheme_id: str, rows: list[dict[str, Any]]) -> None:
    """按 schema 写入，行按项目名排序（保证改动在 git 中可读）。"""
    directory = scheme_dir(data_dir, scheme_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / config.SCHEME_LABELS_FILE
    tmp = path.with_name(path.name + ".tmp")
    rows = sorted(rows, key=lambda r: r["full_name"].casefold())
    pq.write_table(pa.Table.from_pylist(rows, schema=schema.LABELS), tmp, compression="zstd")
    os.replace(tmp, path)


def scheme_ids(data_dir: Path) -> list[str]:
    """data_dir 下全部体系的编号，按（meta 里的 order，编号）排序，页面也按这个顺序列出。"""
    root = data_dir / config.SCHEMES_DIR_NAME
    if not root.is_dir():
        return []

    def order(scheme_id: str) -> tuple[int, str]:
        try:
            meta = read_meta(data_dir, scheme_id) or {}
        except json.JSONDecodeError:
            meta = {}
        value = meta.get("order")
        return (value if isinstance(value, int) else DEFAULT_ORDER, scheme_id)

    return sorted((p.name for p in root.iterdir() if p.is_dir()), key=order)


def build_rows(members: dict[str, list[str]], primary: bool) -> list[dict[str, Any]]:
    """项目名 → 节点编号列表，变成标注行。有主分类的体系取第一个为主分类，其余为关联分类。"""
    rows = []
    for name, ids in members.items():
        ids = list(dict.fromkeys(ids))
        rows.append(
            {
                "full_name": name,
                "category": ids[0] if primary else None,
                "related": ids[1:] if primary else ids,
            }
        )
    return rows


def prune_nodes(nodes: list[dict[str, Any]], used: set[str]) -> list[dict[str, Any]]:
    """只保留被用到的节点及其上级，顺序不变。"""
    parent = {n["id"]: n.get("parent") for n in nodes}
    keep: set[str] = set()
    for node_id in used:
        while node_id is not None and node_id not in keep:
            keep.add(node_id)
            node_id = parent.get(node_id)
    return [n for n in nodes if n["id"] in keep]


def reconcile(
    rows: list[dict[str, Any]], names: list[str], aliases: dict[str, list[str]]
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """让标注的项目名与总榜一致，返回（新的行，改名数，被丢弃的项目名）。

    项目改名后按 `aliases`（当前名称 -> 采集中出现过的全部名称）换成当前名称；
    已不在总榜里的项目，其标注被丢弃。比较时忽略大小写，结果保存总榜里的写法。
    """
    current = {n.casefold(): n for n in names}
    renamed_to = {a.casefold(): cur for cur, olds in aliases.items() for a in olds}
    kept: dict[str, dict[str, Any]] = {}
    renamed = 0
    dropped: list[str] = []
    for row in rows:
        key = row["full_name"].casefold()
        name = current.get(key) or renamed_to.get(key)
        if name is None or name.casefold() in kept:
            dropped.append(row["full_name"])
            continue
        renamed += name != row["full_name"]
        kept[name.casefold()] = row | {"full_name": name}
    return list(kept.values()), renamed, dropped


def carry(data_dir: Path, staging: Path, names: list[str], aliases: dict[str, list[str]]) -> None:
    """全部体系沿用到暂存目录：改名的项目换成当前名称，已不在总榜里的项目其标注被丢弃。"""
    for scheme_id in scheme_ids(data_dir):
        meta = read_meta(data_dir, scheme_id)
        if meta is None:
            continue
        write_meta(staging, scheme_id, meta)
        rows, renamed, dropped = reconcile(read_rows(data_dir, scheme_id), names, aliases)
        if not (scheme_dir(data_dir, scheme_id) / config.SCHEME_LABELS_FILE).exists():
            continue  # 只有体系定义、还没有标注
        if renamed or dropped:
            log.info(
                "分类体系 %s：%d 个项目改名，%d 个项目已不在总榜而被丢弃",
                scheme_id,
                renamed,
                len(dropped),
            )
        write_rows(staging, scheme_id, rows)
