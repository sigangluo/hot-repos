"""路径与全局常量。其他模块不重复定义这些值。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"
WEB_DATA_DIR = ROOT / "web" / "public" / "data"

# 数据契约版本。表结构或口径发生不兼容变化时加一，并同步 docs/data-model.md。
SCHEMA_VERSION = 1

# data/ 下的文件名。
REPOS_FILE = "repos.parquet"
STAR_WEEKS_FILE = "star_weeks.parquet"
RANK_HISTORY_FILE = "rank_history.parquet"
MANIFEST_FILE = "manifest.json"
# 项目分类是可选数据：两个文件要么同时存在，要么都没有。
CLASSIFICATION_FILE = "classification.parquet"
TAXONOMY_FILE = "taxonomy.json"
TABLE_FILES = {
    "repos": REPOS_FILE,
    "star_weeks": STAR_WEEKS_FILE,
    "rank_history": RANK_HISTORY_FILE,
}

# 仓库根目录下识别的 README 文件名，按优先级排列（GitHub 文件名区分大小写，只取 Markdown 系）。
README_FILENAMES = ("README.md", "readme.md", "Readme.md", "README.markdown")

# 官方 Star 周分布接口每页返回的周数。
STAR_WEEKS_PER_PAGE = 30

# ---------- GitHub 接口 ----------
GITHUB_REST_URL = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
# 周 Star 分布接口需要的 API 版本。
STAR_WEEKS_API_VERSION = "2026-03-10"

# ---------- 采集参数默认值 ----------
DEFAULT_MAX_AGE_HOURS = 24  # 缓存有效时长，超过则重新抓取
CACHE_RETENTION_DAYS = 30  # 缓存日志里超过这么久的记录在运行结束时清理
REQUESTS_PER_SECOND = 12  # 所有请求（含重试）合计的上限，低于 GitHub 的次级限流
SEARCH_INTERVAL_SECONDS = 2.1  # 搜索接口两次请求的最小间隔（搜索额度为每分钟 30 次）
GRAPHQL_BATCH_SIZE = 10  # 一次 GraphQL 查询包含的仓库数
GRAPHQL_CONCURRENCY = 8
REST_CONCURRENCY = 32  # 贡献者数与周 Star 分布的并发数

# ---------- Trending ----------
TRENDING_DIR_NAME = "trending"  # data/ 下存放每日快照的子目录，每天一个 YYYY-MM-DD.parquet
TRENDING_URL = "https://github.com/trending"
# 时间段 -> 页面上"新增 Star"文字中的时间词。解析时用它核对页面确实按所请求的时间段返回。
TRENDING_PERIODS = {"daily": "today", "weekly": "this week", "monthly": "this month"}
# 除"全部语言"外，每天另外抓取的语言：Trending 地址中的写法 -> 显示名。
TRENDING_LANGUAGES = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "c++": "C++",
    "c": "C",
    "c#": "C#",
    "swift": "Swift",
}
TRENDING_ALL = "all"  # "全部语言"在数据中的取值
TRENDING_MIN_ENTRIES = 5  # "全部语言"的每个时间段至少应有这么多条，否则认为页面结构变了，不写入
TRENDING_REQUESTS_PER_SECOND = 1  # 面向网页而非接口，保持克制

# ---------- 总榜搜索 ----------
# 搜索接口单次查询最多返回 1000 条，因此按 Star 区间从高到低分段，每段最多取 900 条。
SEARCH_PAGE_SIZE = 100
SEARCH_SHARD_LIMIT = 900
SEARCH_STAR_FLOOR = 10_000  # 区间下界的上限；区间 [floor, upper] 内项目不足一段时一次取完
