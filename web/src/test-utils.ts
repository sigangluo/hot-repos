// 测试用的数据构造工具。
import { applyScheme, buildRepos, type Repo } from './data/model';
import { buildTaxonomy } from './data/taxonomy';
import type { RepoColumns, SchemeFile, SchemeInfo } from './data/types';

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

/** 生成项目；给出分类体系文件时，把它应用到全部项目。 */
export function makeRepos(rows: RowOverrides[], file: SchemeFile | null = null): Repo[] {
  const repos = buildRepos(columns(rows), NOW);
  if (file) applyScheme(repos, { file, taxonomy: buildTaxonomy(file) });
  return repos;
}

/** 一个分类体系的简介。 */
export function schemeInfo(changes: Partial<SchemeInfo> = {}): SchemeInfo {
  return {
    id: 'site', name: '测试体系', summary: '用于测试的体系', method: 'model', source: null,
    created: '2026-01-01', updated: '2026-01-09', as_of: null,
    note: null, primary: true, classified: 2, ...changes,
  };
}

/** 一份小的分类数据：开发 › 工具 › 命令行、开发 › 编辑器、人工智能 › 智能体；参数是各行的（主分类, 关联, 形态）下标。 */
export function classification(rows: [number | null, number[], number[]][]): SchemeFile {
  return {
    nodes: [
      ['dev', -1, '开发', '写代码的工具与方法', null],
      ['dev.tools', 0, '工具', '命令行与编辑器', '数据库归 data'],
      ['dev.tools.cli', 1, '命令行', null, null],
      ['dev.editor', 0, '编辑器', null, null],
      ['ai', -1, '人工智能', null, null],
      ['ai.agent', 4, '智能体', null, null],
    ],
    forms: [['app', '应用', '直接使用的应用'], ['library', '库', '供程序引用的代码库']],
    category: rows.map(([c]) => c),
    related: rows.map(([, r]) => r),
    form: rows.map(([, , f]) => f),
  };
}
