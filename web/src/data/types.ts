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
  /** 可选的分类体系，按页面列出的顺序；没有分类数据时为空数组。 */
  schemes: SchemeInfo[];
}

/** 分类体系的简介（来自 meta.json），在加载体系文件之前就能列出并介绍它们。 */
export interface SchemeInfo {
  id: string;
  name: string;
  summary: string;
  /** 标注方式：model 语言模型判断，manual 研究者人工标注，curated 来源方人工策展。 */
  method: 'model' | 'manual' | 'curated';
  /** 外部来源的出处与许可。 */
  source: SchemeSource | null;
  /** 体系的创建日期（YYYY-MM-DD）：来源仓库创建或数据集发布的日期。 */
  created: string;
  /** 体系内容最近一次变化的日期（YYYY-MM-DD）：来源最近一次相关提交或更新。 */
  updated: string;
  /** 取得来源数据的日期。 */
  as_of: string | null;
  /** 使用时需要注意的说明（如数据的年代、可信度），没有则为 null。 */
  note: string | null;
  /** 每个已标注的项目是否都有主分类；没有主分类的体系，一个项目只有若干并列的分类。 */
  primary: boolean;
  /** 体系里已有标注的项目数。 */
  classified: number;
}

export interface SchemeSource {
  name: string;
  url: string;
  license: string;
  attribution?: string;
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
 * scheme-<编号>.json：一个分类体系的节点，及每个项目的分类。
 * `category` / `related` 与 repos.json 的行对齐，值是 `nodes` 的下标；
 * 没有标注的项目 `category` 为 null，`related` 为空数组；
 * 没有主分类的体系，`category` 全为 null，项目的全部分类都在 `related` 里。
 */
export interface SchemeFile {
  /** [编号, 父节点在 nodes 中的下标（一级为 -1）, 名称, 收录说明, 排除说明]，父节点排在子节点之前；说明没有则为 null。 */
  nodes: [string, number, string, string | null, string | null][];
  category: (number | null)[];
  related: number[][];
}
