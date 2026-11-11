"""data/ → web/public/data/：页面用的静态数据文件。

数据均为列式（`{列名: [每行的值]}`，各列等长且行顺序一致；除 trending 外按名次升序；
`trending.json` 的列在 `rows` 下，外层另有快照日期、抓取时间和语言列表；
`scheme-<编号>.json` 外层另有体系的节点，见下），
列名不在每行重复，体积约为按行存储的一半：

| 文件 | 内容 | 加载时机 |
|---|---|---|
| `meta.json` | 快照日期、各部分获取时间、数量、最新 Trending 快照日期、各分类体系的简介与覆盖数 | 首屏 |
| `repos.json` | 表格、筛选、搜索所需的精简列 | 首屏 |
| `scheme-<编号>.json` | 一个分类体系的节点，及每个项目的主分类、关联分类（与 repos.json 行对齐）；没有标注的体系不生成 | 默认体系在首屏，其余在切换到它时；失败时页面不带分类 |
| `details.json` | 语言构成、赞助链接、README 文件名等详情字段 | 首次打开详情时 |
| `weeks.json` | 官方周 Star 分布 | 首屏之后（迷你图）与详情 |
| `trending.json` | 最新一天的 Trending 快照；还没有快照时不生成 | 首次打开“近期热点”时 |

时间戳一律为 Unix 秒；没有值为 null。字段含义见 docs/data-model.md，页面端的类型见 web/src/data/types.ts。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import cache, config, schemes, store, trending
from .validate import validate

META_FILE = "meta.json"
REPOS_FILE = "repos.json"
DETAILS_FILE = "details.json"
WEEKS_FILE = "weeks.json"
TRENDING_FILE = "trending.json"
SCHEME_FILE_PREFIX = "scheme-"

# 直接取自 repos.parquet 的列（时间列转为 Unix 秒）。
REPO_COLUMNS = [
    "rank",
    "full_name",
    "description",
    "owner_type",
    "created_at",
    "pushed_at",
    "is_archived",
    "is_fork",
    "is_template",
    "stars",
    "forks",
    "watchers",
    "open_issues",
    "closed_issues",
    "open_prs",
    "merged_prs",
    "discussions",
    "primary_language",
    "topics",
    "license",
    "commit_count",
    "contributors",
    "release_count",
    "latest_release_at",
    "disk_usage_kb",
]
# 由其他列推出的布尔列，供筛选使用。
REPO_FLAGS = ("has_homepage", "has_funding", "has_readme")
DETAIL_COLUMNS = [
    "homepage",
    "default_branch",
    "updated_at",
    "fetched_at",
    "discussions_enabled",
    "languages",
    "funding",
    "readme_path",
    "star_weeks_fetched_at",
    "star_weeks_pages_fetched",
    "star_weeks_pages_total",
]


# 取自 Trending 快照的列（时间列转为 Unix 秒）。
TRENDING_COLUMNS = [
    "since",
    "language",
    "rank",
    "full_name",
    "description",
    "repo_language",
    "stars",
    "forks",
    "period_stars",
    "built_by",
]


class ExportError(RuntimeError):
    """待导出的数据未通过校验。"""


def _epoch(value: Any) -> Any:
    return int(value.timestamp()) if isinstance(value, datetime) else value


def _columns(rows: list[dict], names: list[str]) -> dict[str, list]:
    return {name: [_epoch(r[name]) for r in rows] for name in names}


def _trending(data_dir: Path) -> dict[str, Any] | None:
    """最新一天的 Trending 快照；还没有快照时为 None。"""
    files = trending.snapshot_files(data_dir / config.TRENDING_DIR_NAME)
    if not files:
        return None
    rows = trending.read_snapshot(files[-1])
    present = {r["language"] for r in rows}
    # 语言按配置顺序排列，“全部语言”在前；快照里出现但配置已删除的语言排在最后。
    known = [(config.TRENDING_ALL, "全部语言"), *config.TRENDING_LANGUAGES.items()]
    languages = [[k, label] for k, label in known if k in present]
    languages += [[k, k] for k in sorted(present - {k for k, _ in known})]
    return {
        "snapshot_date": rows[0]["snapshot_date"].isoformat(),
        "captured_at": _epoch(rows[0]["captured_at"]),
        "languages": languages,
        "rows": _columns(rows, TRENDING_COLUMNS),
    }


def scheme_file_name(scheme_id: str) -> str:
    return f"{SCHEME_FILE_PREFIX}{scheme_id}.json"


def _scheme(
    meta: dict[str, Any], by_name: dict[str, dict], repos: list[dict]
) -> dict[str, Any]:
    """返回体系文件的内容。

    节点导出为 [编号, 父节点在 nodes 中的下标（一级为 -1）, 名称, 收录说明, 排除说明]（说明没有则为 null）；
    项目一列一列地引用节点的下标，与 repos 行对齐，没有标注的项目为 null（关联分类为空列表）。
    """
    node_index = {n["id"]: i for i, n in enumerate(meta["nodes"])}
    rows = [by_name.get(r["full_name"]) for r in repos]
    return {
        "nodes": [
            [
                n["id"],
                node_index[n["parent"]] if n.get("parent") is not None else -1,
                n["label"],
                n.get("guidance", {}).get("includes"),
                n.get("guidance", {}).get("excludes"),
            ]
            for n in meta["nodes"]
        ],
        "category": [node_index[r["category"]] if r and r["category"] else None for r in rows],
        "related": [[node_index[c] for c in r["related"]] if r else [] for r in rows],
    }


def _scheme_summary(scheme_id: str, meta: dict[str, Any], classified: int) -> dict[str, Any]:
    """meta.json 里关于体系的部分：页面在加载体系文件之前就能列出并介绍它们。"""
    return {
        "id": scheme_id,
        "name": meta["name"],
        "summary": meta["summary"],
        "method": meta["method"],
        "source": meta.get("source"),
        "created": meta["created"],
        "updated": meta["updated"],
        "as_of": meta.get("as_of"),
        "note": meta.get("note"),
        "primary": meta["primary"],
        "classified": classified,
    }


def _schemes(
    data_dir: Path, repos: list[dict]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """返回（meta 里的体系列表，体系文件）；只含已有标注的体系。"""
    summaries: list[dict[str, Any]] = []
    files: dict[str, dict[str, Any]] = {}
    for scheme_id in schemes.scheme_ids(data_dir):
        meta = schemes.read_meta(data_dir, scheme_id)
        by_name = {r["full_name"]: r for r in schemes.read_rows(data_dir, scheme_id)}
        if meta is None or not by_name:  # 只有体系定义、还没有标注时，页面不列出
            continue
        file = _scheme(meta, by_name, repos)
        classified = sum(
            bool(c is not None or rel)
            for c, rel in zip(file["category"], file["related"], strict=True)
        )
        summaries.append(_scheme_summary(scheme_id, meta, classified))
        files[scheme_file_name(scheme_id)] = file
    return summaries, files


def build(data_dir: Path) -> dict[str, Any]:
    """读取 data_dir，返回各输出文件的内容。"""
    repos = sorted(store.read_rows(data_dir, "repos"), key=lambda r: r["rank"])
    manifest = store.read_manifest(data_dir) or {}

    repo_cols = _columns(repos, REPO_COLUMNS)
    repo_cols["has_homepage"] = [r["homepage"] is not None for r in repos]
    repo_cols["has_funding"] = [bool(r["funding"]) for r in repos]
    repo_cols["has_readme"] = [r["readme_path"] is not None for r in repos]

    detail_cols = _columns(repos, DETAIL_COLUMNS)
    detail_cols["languages"] = [[[x["name"], x["bytes"]] for x in r["languages"]] for r in repos]
    detail_cols["funding"] = [[[x["platform"], x["url"]] for x in r["funding"]] for r in repos]

    scheme_summaries, scheme_files = _schemes(data_dir, repos)

    weeks_by_repo: dict[str, list[dict]] = {}
    for w in store.read_rows(data_dir, "star_weeks"):
        weeks_by_repo.setdefault(w["full_name"], []).append(w)
    starts: list[str | None] = []
    stars: list[list[int] | None] = []
    for r in repos:
        weeks = weeks_by_repo.get(r["full_name"])  # 已按周升序，且连续（validate 保证）
        starts.append(weeks[0]["week_start"].isoformat() if weeks else None)
        stars.append([w["stars"] for w in weeks] if weeks else None)

    fetched = [r["fetched_at"] for r in repos]
    weeks_fetched = [r["star_weeks_fetched_at"] for r in repos if r["star_weeks_fetched_at"]]
    trending_page = _trending(data_dir)
    meta = {
        "schema_version": manifest["schema_version"],
        "snapshot_date": manifest["snapshot_date"],
        "board_size": manifest["board_size"],
        "repos": len(repos),
        "missing": len(manifest["missing"]),
        "rank_captured_at": _epoch(datetime.fromisoformat(manifest["rank_captured_at"])),
        "repos_fetched_at": [_epoch(min(fetched)), _epoch(max(fetched))] if fetched else None,
        "star_weeks_fetched_at": (
            [_epoch(min(weeks_fetched)), _epoch(max(weeks_fetched))] if weeks_fetched else None
        ),
        "star_weeks_per_page": manifest["star_weeks_per_page"],
        "trending_date": trending_page["snapshot_date"] if trending_page else None,
        "schemes": scheme_summaries,
    }
    files = {
        META_FILE: meta,
        REPOS_FILE: repo_cols,
        DETAILS_FILE: detail_cols,
        WEEKS_FILE: {"week_start": starts, "stars": stars},
    }
    if trending_page:
        files[TRENDING_FILE] = trending_page
    files.update(scheme_files)
    return files


def export(data_dir: Path = config.DATA_DIR, out_dir: Path = config.WEB_DATA_DIR) -> dict[str, int]:
    """校验并导出，返回各文件的字节数。校验不通过时不写任何文件。"""
    problems = validate(data_dir)
    if problems:
        raise ExportError("data/ 未通过校验，未导出：\n" + "\n".join(problems[:20]))
    files = build(data_dir)
    # 清除以前导出的旧文件，避免页面展示过期数据。
    if TRENDING_FILE not in files:
        (out_dir / TRENDING_FILE).unlink(missing_ok=True)
    for stale in out_dir.glob(f"{SCHEME_FILE_PREFIX}*.json"):
        if stale.name not in files:
            stale.unlink()
    sizes = {}
    for name, content in files.items():
        cache.write_json(out_dir / name, content, compact=True)
        sizes[name] = (out_dir / name).stat().st_size
    return sizes


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
