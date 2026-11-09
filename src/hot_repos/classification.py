"""项目分类：目录（data/taxonomy.json）与分类结果（data/classification.parquet）。

两者都是可选数据，由人工或外部流程产生，采集命令不生成分类；采集只负责让结果和总榜的项目名保持一致
（见 `reconcile`）。表结构见 schema.CLASSIFICATION，口径见 docs/data-model.md。
"""

import json
import os
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from . import cache, config, schema


def read_taxonomy(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / config.TAXONOMY_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_taxonomy(data_dir: Path, taxonomy: dict[str, Any]) -> None:
    cache.write_json(data_dir / config.TAXONOMY_FILE, taxonomy, indent=1)


def read_rows(data_dir: Path) -> list[dict[str, Any]]:
    """读取分类结果；文件不存在时返回空列表。"""
    path = data_dir / config.CLASSIFICATION_FILE
    return pq.read_table(path).to_pylist() if path.exists() else []


def write_rows(data_dir: Path, rows: list[dict[str, Any]]) -> None:
    """按 schema 写入，行按项目名排序（保证改动在 git 中可读）。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / config.CLASSIFICATION_FILE
    tmp = path.with_name(path.name + ".tmp")
    rows = sorted(rows, key=lambda r: r["full_name"].casefold())
    pq.write_table(
        pa.Table.from_pylist(rows, schema=schema.CLASSIFICATION), tmp, compression="zstd"
    )
    os.replace(tmp, path)


def reconcile(
    rows: list[dict[str, Any]], names: list[str], aliases: dict[str, list[str]]
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """让分类结果的项目名与总榜一致，返回（新的行，改名数，被丢弃的项目名）。

    项目改名后按 `aliases`（当前名称 -> 采集中出现过的全部名称）换成当前名称；
    已不在总榜里的项目，其分类结果被丢弃。比较时忽略大小写，结果保存总榜里的写法。
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
