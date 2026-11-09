// 测试用的数据构造工具。
import { buildRepos, type Repo } from './data/model';
import type { RepoColumns } from './data/types';

export const NOW = Date.UTC(2026, 0, 10);
const DAY = 86_400;

const DEFAULTS: Record<keyof RepoColumns, unknown> = {
  rank: 1, full_name: 'o/r', description: null, owner_type: 'Organization',
  created_at: NOW / 1000 - 400 * DAY, pushed_at: NOW / 1000 - 2 * DAY, is_archived: false,
  is_fork: false, is_template: false, stars: 100, forks: 1, watchers: 1, open_issues: 0,
  closed_issues: 0, open_prs: 0, merged_prs: 0, discussions: 0, primary_language: 'Python',
  topics: [], license: 'MIT', commit_count: 5, contributors: 3, release_count: 0,
  latest_release_at: null, disk_usage_kb: 10, has_homepage: false, has_funding: false,
  has_readme: true,
};

export type RowOverrides = Partial<Record<keyof RepoColumns, unknown>>;

/** 用列式默认值加每行的覆盖项，生成页面数据。 */
export function columns(rows: RowOverrides[]): RepoColumns {
  const out: Record<string, unknown[]> = {};
  for (const key of Object.keys(DEFAULTS) as (keyof RepoColumns)[]) {
    out[key] = rows.map((r) => (key in r ? r[key] : DEFAULTS[key]));
  }
  return out as unknown as RepoColumns;
}

export function makeRepos(rows: RowOverrides[]): Repo[] {
  return buildRepos(columns(rows), NOW);
}
