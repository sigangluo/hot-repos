"""数据契约：data/ 下各文件的结构。字段含义与口径见 docs/data-model.md。

表结构只在这里定义；写入、校验、导出都以它为准。
"""

import pyarrow as pa

TIMESTAMP = pa.timestamp("us", tz="UTC")


def _f(name: str, type_: pa.DataType, nullable: bool = False) -> pa.Field:
    return pa.field(name, type_, nullable=nullable)


LANGUAGE = pa.struct([_f("name", pa.string()), _f("bytes", pa.int64())])
FUNDING_LINK = pa.struct([_f("platform", pa.string()), _f("url", pa.string())])

REPOS = pa.schema(
    [
        # 标识与名次
        _f("full_name", pa.string()),
        _f("rank", pa.int32()),
        # 基本信息
        _f("description", pa.string(), True),
        _f("homepage", pa.string(), True),
        _f("owner_type", pa.string()),
        _f("created_at", TIMESTAMP),
        _f("pushed_at", TIMESTAMP, True),
        _f("updated_at", TIMESTAMP),
        _f("is_archived", pa.bool_()),
        _f("is_fork", pa.bool_()),
        _f("is_template", pa.bool_()),
        _f("disk_usage_kb", pa.int64(), True),
        # 规模与互动
        _f("stars", pa.int64()),
        _f("forks", pa.int64()),
        _f("watchers", pa.int64()),
        _f("open_issues", pa.int64()),
        _f("closed_issues", pa.int64()),
        _f("open_prs", pa.int64()),
        _f("merged_prs", pa.int64()),
        _f("discussions_enabled", pa.bool_()),
        _f("discussions", pa.int64()),
        # 技术画像
        _f("primary_language", pa.string(), True),
        _f("languages", pa.list_(LANGUAGE)),
        _f("topics", pa.list_(pa.string())),
        _f("license", pa.string(), True),
        _f("default_branch", pa.string(), True),
        # 活跃与发布
        _f("commit_count", pa.int64(), True),
        _f("contributors", pa.int64(), True),
        _f("release_count", pa.int64()),
        _f("latest_release_tag", pa.string(), True),
        _f("latest_release_at", TIMESTAMP, True),
        _f("funding", pa.list_(FUNDING_LINK)),
        _f("readme_path", pa.string(), True),
        # 获取时点
        _f("fetched_at", TIMESTAMP),
        _f("star_weeks_fetched_at", TIMESTAMP, True),
        _f("star_weeks_pages_fetched", pa.int32(), True),
        _f("star_weeks_pages_total", pa.int32(), True),
    ]
)

STAR_WEEKS = pa.schema(
    [
        _f("full_name", pa.string()),
        _f("week_start", pa.date32()),
        _f("stars", pa.int64()),
        _f("days", pa.list_(pa.int32())),
    ]
)

RANK_HISTORY = pa.schema(
    [
        _f("snapshot_date", pa.date32()),
        _f("rank", pa.int32()),
        _f("full_name", pa.string()),
        _f("stars", pa.int64()),
        _f("captured_at", TIMESTAMP),
    ]
)

# Trending 的每日快照，一天一个文件（data/trending/YYYY-MM-DD.parquet）。
# 不属于 TABLES：它按日期分文件追加，不随总榜一起整体发布。
TRENDING = pa.schema(
    [
        _f("snapshot_date", pa.date32()),
        _f("since", pa.string()),
        _f("language", pa.string()),
        _f("rank", pa.int32()),
        _f("full_name", pa.string()),
        _f("description", pa.string(), True),
        _f("repo_language", pa.string(), True),
        _f("stars", pa.int64()),
        _f("forks", pa.int64()),
        _f("period_stars", pa.int64()),
        _f("built_by", pa.list_(pa.string())),
        _f("captured_at", TIMESTAMP),
    ]
)

# 项目分类结果（data/classification.parquet），目录本身在 data/taxonomy.json。
# 可选数据，不属于 TABLES：它不随总榜采集整体发布，采集时只按项目名对齐。
CLASSIFICATION = pa.schema(
    [
        _f("full_name", pa.string()),
        _f("category", pa.string()),
        _f("related", pa.list_(pa.string())),
        _f("forms", pa.list_(pa.string())),
        _f("summary", pa.string()),
        _f("review_reason", pa.string(), True),
    ]
)

# data/ 下的 Parquet 表，键为不含扩展名的文件名。
TABLES = {"repos": REPOS, "star_weeks": STAR_WEEKS, "rank_history": RANK_HISTORY}

# manifest.json 的字段及其 Python 类型（时间一律为带时区的 ISO 8601 字符串）。
MANIFEST_FIELDS: dict[str, type] = {
    "schema_version": int,
    "snapshot_date": str,
    "board_size": int,
    "rank_captured_at": str,
    "run_at": str,
    "star_weeks_per_page": int,
    "aliases": dict,
    "missing": list,
}
