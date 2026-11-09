// 页面数据的类型，对应 `hot-repos export` 生成的 web/public/data/*.json。
// 字段与 src/hot_repos/export_web.py 一一对应，tests/test_export.py 会检查两边一致。
// 每个文件是列式的 `{列名: [每行的值]}`，各列等长，按名次升序；时间戳为 Unix 秒；缺失为 null。

export interface Meta {
  schema_version: number;
  snapshot_date: string;
  board_size: number;
  repos: number;
  missing: number;
  rank_captured_at: number;
  repos_fetched_at: [number, number] | null;
  star_weeks_fetched_at: [number, number] | null;
  star_weeks_per_page: number;
  /** 最新一天的 Trending 快照日期；还没有快照时为 null。 */
  trending_date: string | null;
  /** 已分类的项目数；为 0 表示没有分类数据。 */
  classified: number;
}

export interface RepoColumns {
  rank: number[];
  full_name: string[];
  description: (string | null)[];
  owner_type: string[];
  created_at: number[];
  pushed_at: (number | null)[];
  is_archived: boolean[];
  is_fork: boolean[];
  is_template: boolean[];
  stars: number[];
  forks: number[];
  watchers: number[];
  open_issues: number[];
  closed_issues: number[];
  open_prs: number[];
  merged_prs: number[];
  discussions: number[];
  primary_language: (string | null)[];
  topics: string[][];
  license: (string | null)[];
  commit_count: (number | null)[];
  contributors: (number | null)[];
  release_count: number[];
  latest_release_at: (number | null)[];
  disk_usage_kb: (number | null)[];
  has_homepage: boolean[];
  has_funding: boolean[];
  has_readme: boolean[];
}

export interface DetailColumns {
  homepage: (string | null)[];
  default_branch: (string | null)[];
  updated_at: number[];
  fetched_at: number[];
  discussions_enabled: boolean[];
  languages: [string, number][][];
  funding: [string, string][][];
  readme_path: (string | null)[];
  star_weeks_fetched_at: (number | null)[];
  star_weeks_pages_fetched: (number | null)[];
  star_weeks_pages_total: (number | null)[];
  /** 分类的一句话简介；未分类为 null。 */
  summary: (string | null)[];
  /** 需要复核的原因；无需复核或未分类为 null。 */
  review_reason: (string | null)[];
}

export interface WeeksColumns {
  week_start: (string | null)[];
  stars: (number[] | null)[];
}

export interface TrendingColumns {
  since: string[];
  language: string[];
  rank: number[];
  full_name: string[];
  description: (string | null)[];
  repo_language: (string | null)[];
  stars: number[];
  forks: number[];
  period_stars: number[];
  built_by: string[][];
}

/** trending.json：最新一天的 Trending 快照。 */
export interface TrendingFile {
  snapshot_date: string;
  captured_at: number;
  /** [榜单语言的键, 显示名]，“全部语言”在前。 */
  languages: [string, string][];
  rows: TrendingColumns;
}

/**
 * classification.json：分类目录与每个项目的分类。
 * `category` / `related` / `form` 与 repos.json 的行对齐，值是 `nodes` / `forms` 的下标；
 * 未分类的项目 `category` 为 null，`related` 与 `form` 为空数组。
 */
export interface ClassificationFile {
  /** 目录附带的说明（如分类的来源与可信度），原样展示；没有则为 null。 */
  note: string | null;
  /** [编号, 父节点在 nodes 中的下标（一级为 -1）, 名称]，父节点排在子节点之前。 */
  nodes: [string, number, string][];
  /** [形态编号, 名称]。 */
  forms: [string, string][];
  category: (number | null)[];
  related: number[][];
  form: number[][];
}
