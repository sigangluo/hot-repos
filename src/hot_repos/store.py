"""读写 data/：按 schema 写 Parquet、合并历史名次、整体发布。"""

import json
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from . import cache, config, schema


def read_rows(data_dir: Path, table: str) -> list[dict[str, Any]]:
    """读取一张表；文件不存在时返回空列表。"""
    path = data_dir / config.TABLE_FILES[table]
    return pq.read_table(path).to_pylist() if path.exists() else []


def write_rows(data_dir: Path, table: str, rows: list[dict[str, Any]]) -> None:
    """按 schema 校验并写入；字段缺失、多余或违反非空约束时抛出异常。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / config.TABLE_FILES[table]
    tmp = path.with_name(path.name + ".tmp")
    pq.write_table(pa.Table.from_pylist(rows, schema=schema.TABLES[table]), tmp, compression="zstd")
    os.replace(tmp, path)


def write_manifest(data_dir: Path, manifest: dict[str, Any]) -> None:
    cache.write_json(data_dir / config.MANIFEST_FILE, manifest, indent=2)


def read_manifest(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / config.MANIFEST_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def merge_rank_history(
    existing: list[dict[str, Any]], snapshot: list[dict[str, Any]], snapshot_date: date
) -> list[dict[str, Any]]:
    """加入新快照；同一天重复运行时替换当天的旧快照。"""
    kept = [r for r in existing if r["snapshot_date"] != snapshot_date]
    return sorted(kept + snapshot, key=lambda r: (r["snapshot_date"], r["rank"]))


def publish(staging: Path, data_dir: Path) -> None:
    """把暂存目录中的数据文件替换到 data_dir。

    先把全部文件复制成同目录下的临时文件（磁盘写满等失败都发生在这一步，此时 data_dir 原样不变），
    再依次用 os.replace 换上。后一步只剩几次重命名，被中断的窗口极小。
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    optional = (config.CLASSIFICATION_FILE, config.TAXONOMY_FILE)
    filenames = (
        *config.TABLE_FILES.values(),
        config.MANIFEST_FILE,
        *(f for f in optional if (staging / f).exists()),
    )
    copied: list[Path] = []
    try:
        for filename in filenames:
            tmp = data_dir / (filename + ".tmp")
            copied.append(tmp)
            shutil.copyfile(staging / filename, tmp)
    except BaseException:
        for tmp in copied:
            tmp.unlink(missing_ok=True)
        raise
    for filename in filenames:
        os.replace(data_dir / (filename + ".tmp"), data_dir / filename)
