"""同步外部分类体系：取来源 → 按项目名对上总榜 → 校验 → 写入 data/schemes/<编号>/。

只保存“总榜里的哪个项目属于来源里的哪个类”，来源里没有出现在总榜的项目、没有用到的分类都不保存。
任何一步失败，该体系已有的数据保持原样。
"""

import logging
from datetime import date
from pathlib import Path

from . import schemes, store
from .sources import Collected, Fetcher, SourceError, registry
from .validate import check_scheme_meta, check_scheme_rows

log = logging.getLogger(__name__)


def match(
    members: dict[str, list[str]], names: list[str], aliases: dict[str, list[str]]
) -> dict[str, list[str]]:
    """把来源里的项目名对到总榜的写法（忽略大小写；改名过的项目按 aliases 对到当前名称）。"""
    current = {n.casefold(): n for n in names}
    renamed_to = {a.casefold(): cur for cur, olds in aliases.items() for a in olds}
    matched: dict[str, list[str]] = {}
    for source_name, ids in members.items():
        board = current.get(source_name.casefold()) or renamed_to.get(source_name.casefold())
        if board is not None:
            matched.setdefault(board, []).extend(ids)
    return matched


def apply(
    collected: Collected, names: list[str], aliases: dict[str, list[str]], today: date
) -> tuple[dict, list[dict]]:
    """返回（体系定义，标注行）。对不上任何项目、或结果没通过校验时抛出 SourceError。"""
    primary = collected.meta["primary"]
    matched = match(collected.members, names, aliases)
    if not matched:
        raise SourceError("来源里的项目没有一个对得上总榜（来源的格式可能变了）")
    rows = schemes.build_rows(matched, primary)
    used = {i for r in rows for i in [r["category"], *r["related"]] if i is not None}
    unknown = used - {n["id"] for n in collected.meta["nodes"]}
    if unknown:
        raise SourceError(f"项目引用了来源里没有的分类：{sorted(unknown)[:5]}")
    meta = collected.meta | {
        "as_of": today.isoformat(),
        # 一级节点不写 parent 字段（来源模块写成 None 的也一并去掉）
        "nodes": [
            {k: v for k, v in n.items() if k != "parent" or v is not None}
            for n in schemes.prune_nodes(collected.meta["nodes"], used)
        ],
    }
    problems = check_scheme_meta(meta, "scheme.json") + check_scheme_rows(
        rows, meta, set(names), "labels.parquet"
    )
    if problems:
        raise SourceError("同步结果未通过校验：\n" + "\n".join(problems[:10]))
    return meta, rows


def _unchanged(data_dir: Path, scheme_id: str, meta: dict, rows: list[dict]) -> bool:
    """与已有数据相比，除了取得日期（as_of）外没有变化。"""
    old = schemes.read_meta(data_dir, scheme_id)
    if old is None or old | {"as_of": None} != meta | {"as_of": None}:
        return False
    ordered = sorted(rows, key=lambda r: r["full_name"].casefold())
    return schemes.read_rows(data_dir, scheme_id) == ordered


def run(
    data_dir: Path, ids: list[str], fetcher: Fetcher, *, today: date | None = None
) -> dict[str, str]:
    """同步指定的来源（空列表表示全部），返回 {体系编号: 结果说明}；失败的体系其说明以“失败”开头。"""
    sources = registry()
    unknown = [i for i in ids if i not in sources]
    if unknown:
        raise SourceError(f"没有这个来源：{'、'.join(unknown)}（可选：{'、'.join(sources)}）")
    manifest = store.read_manifest(data_dir)
    if manifest is None:
        raise SourceError("data/ 里还没有总榜，请先运行 hot-repos fetch")
    names = [r["full_name"] for r in store.read_rows(data_dir, "repos")]
    today = today or date.today()
    results: dict[str, str] = {}
    for scheme_id in ids or list(sources):
        try:
            collected = sources[scheme_id](fetcher)
            meta, rows = apply(collected, names, manifest["aliases"], today)
        except SourceError as e:
            log.error("%s：%s", scheme_id, e)
            results[scheme_id] = f"失败：{e}"
            continue
        if _unchanged(
            data_dir, scheme_id, meta, rows
        ):  # 只有取得日期变了就不写，避免定时同步产生空提交
            results[scheme_id] = f"{len(rows)} 个项目，{len(meta['nodes'])} 个分类（与上次相同）"
            log.info("%s：%s", scheme_id, results[scheme_id])
            continue
        schemes.write_meta(data_dir, scheme_id, meta)
        schemes.write_rows(data_dir, scheme_id, rows)
        results[scheme_id] = f"{len(rows)} 个项目，{len(meta['nodes'])} 个分类"
        log.info("%s：%s", scheme_id, results[scheme_id])
    return results
