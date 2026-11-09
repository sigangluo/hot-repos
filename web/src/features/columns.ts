import { ageText, compact, date, int } from '../lib/format';
import type { Repo } from '../data/model';
import { PATH_SEPARATOR } from '../data/taxonomy';

/** 表格列。新增一列只需在 COLUMNS 里加一项。 */
export interface Column {
  key: string;
  label: string;
  /** 数值列右对齐。 */
  numeric?: boolean;
  /** 用于排序的取值；缺省表示不可排序。 */
  sortValue?: (r: Repo) => number | string | null;
  /** 单元格文本；缺省按 sortValue 显示。 */
  text?: (r: Repo) => string;
  title?: string;
  /** 只在数据里有分类时才有意义；没有分类数据时列不显示，也不出现在列设置里。 */
  needsClassification?: boolean;
}

export const COLUMNS = [
  { key: 'rank', label: '名次', numeric: true, sortValue: (r) => r.rank, text: (r) => String(r.rank) },
  { key: 'name', label: '项目', sortValue: (r) => r.fullName.toLowerCase() },
  { key: 'stars', label: 'Star', numeric: true, sortValue: (r) => r.stars, text: (r) => int(r.stars) },
  { key: 'spark', label: '近 30 周', title: '官方周 Star 分布，每行独立缩放' },
  { key: 'forks', label: 'Fork', numeric: true, sortValue: (r) => r.forks, text: (r) => compact(r.forks) },
  { key: 'watchers', label: 'Watch', numeric: true, sortValue: (r) => r.watchers, text: (r) => compact(r.watchers) },
  { key: 'contributors', label: '贡献者', numeric: true, sortValue: (r) => r.contributors, text: (r) => int(r.contributors) },
  { key: 'commits', label: '提交数', numeric: true, sortValue: (r) => r.commits, text: (r) => compact(r.commits) },
  { key: 'openIssues', label: '未关 Issue', numeric: true, sortValue: (r) => r.openIssues, text: (r) => compact(r.openIssues) },
  { key: 'openPrs', label: '未合 PR', numeric: true, sortValue: (r) => r.openPrs, text: (r) => compact(r.openPrs) },
  { key: 'releases', label: '发布数', numeric: true, sortValue: (r) => r.releases, text: (r) => compact(r.releases) },
  { key: 'category', label: '分类', title: '主分类', needsClassification: true, sortValue: (r) => r.category.join(PATH_SEPARATOR) || null, text: (r) => r.category.join(PATH_SEPARATOR) || '—' },
  { key: 'language', label: '语言', sortValue: (r) => r.language },
  { key: 'license', label: '许可证', sortValue: (r) => r.license ?? null, text: (r) => r.license ?? '—' },
  { key: 'created', label: '创建', sortValue: (r) => r.createdAt, text: (r) => `${date(r.createdAt)}（${ageText(r.ageDays)}）` },
  { key: 'pushed', label: '最近推送', sortValue: (r) => r.pushedAt, text: (r) => (r.pushedDaysAgo == null ? '—' : `${ageText(r.pushedDaysAgo)}前`) },
] as const satisfies readonly Column[];

export type ColumnKey = (typeof COLUMNS)[number]['key'];

/** 始终显示、不可取消的列。 */
export const PINNED: readonly ColumnKey[] = ['rank', 'name'];

export const DEFAULT_COLUMNS: readonly ColumnKey[] = [
  'rank', 'name', 'stars', 'spark', 'forks', 'contributors', 'category', 'language', 'license', 'created', 'pushed',
];

export function column(key: ColumnKey): Column {
  return COLUMNS.find((c) => c.key === key) as Column;
}

export function sortValue(r: Repo, key: ColumnKey): number | string | null {
  return column(key).sortValue?.(r) ?? null;
}
