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
