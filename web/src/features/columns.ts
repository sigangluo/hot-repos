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
  /** 这一列的含义。每列都必须写：表头的悬停提示、列设置和“名词与口径说明”都用它。 */
  title: string;
  /** 只在数据里有分类时才有意义；没有分类数据时列不显示，也不出现在列设置里。 */
  needsClassification?: boolean;
}

export const COLUMNS = [
  { key: 'rank', label: '名次', title: '总榜名次，按 Star 总数从多到少排列，1 为最多。名次可能不连续：无法获取的仓库（已删除或下架）在名次上留有空档。', numeric: true, sortValue: (r) => r.rank, text: (r) => String(r.rank) },
  { key: 'name', label: '项目', title: '仓库的 owner/repo 名称，下方是仓库描述。', sortValue: (r) => r.fullName.toLowerCase() },
  { key: 'stars', label: 'Star', title: '采集时的 Star 总数，是累计规模，不表示近期增长速度。', numeric: true, sortValue: (r) => r.stars, text: (r) => int(r.stars) },
  { key: 'spark', label: '近 30 周', title: '近 30 周每周新增、且至今仍保留的 Star 数（官方周 Star 分布）。每行独立缩放，只能比较形状，不能比较不同项目的高低。' },
  { key: 'forks', label: 'Fork', title: 'Fork 总数。', numeric: true, sortValue: (r) => r.forks, text: (r) => compact(r.forks) },
  { key: 'watchers', label: 'Watch', title: '订阅了该仓库动态的用户数（watchers）。', numeric: true, sortValue: (r) => r.watchers, text: (r) => compact(r.watchers) },
  { key: 'contributors', label: '贡献者', title: '向仓库贡献过提交的人数，含匿名贡献者。GitHub 对超大仓库不提供，此时显示 —。', numeric: true, sortValue: (r) => r.contributors, text: (r) => int(r.contributors) },
  { key: 'commits', label: '提交数', title: '默认分支上的提交总数。', numeric: true, sortValue: (r) => r.commits, text: (r) => compact(r.commits) },
  { key: 'openIssues', label: '未关 Issue', title: '未关闭的 Issue 数，不含 Pull Request。', numeric: true, sortValue: (r) => r.openIssues, text: (r) => compact(r.openIssues) },
  { key: 'openPrs', label: '未合 PR', title: '未合并且未关闭的 Pull Request 数。', numeric: true, sortValue: (r) => r.openPrs, text: (r) => compact(r.openPrs) },
  { key: 'releases', label: '发布数', title: 'GitHub Releases 的数量。', numeric: true, sortValue: (r) => r.releases, text: (r) => compact(r.releases) },
  { key: 'category', label: '分类', title: '项目的主分类：按它服务的领域归类，路径从一级到最具体的一级；点开详情可看关联分类和各分类的定义。', needsClassification: true, sortValue: (r) => r.category.join(PATH_SEPARATOR) || null, text: (r) => r.category.join(PATH_SEPARATOR) || '—' },
  { key: 'language', label: '语言', title: 'GitHub 判定的主要语言，即代码字节数最多的语言。', sortValue: (r) => r.language },
  { key: 'license', label: '许可证', title: 'GitHub 识别出的许可证标识（SPDX）。NOASSERTION 表示识别到了许可证文件但无法确定类型；— 表示没有识别出许可证。', sortValue: (r) => r.license ?? null, text: (r) => r.license ?? '—' },
  { key: 'created', label: '创建', title: '仓库在 GitHub 上的创建时间（UTC），括号内是到数据获取时的年龄。', sortValue: (r) => r.createdAt, text: (r) => `${date(r.createdAt)}（${ageText(r.ageDays)}）` },
  { key: 'pushed', label: '最近推送', title: '最近一次向仓库推送代码的时间，括号内是距数据获取时的时长。', sortValue: (r) => r.pushedAt, text: (r) => (r.pushedDaysAgo == null ? '—' : `${ageText(r.pushedDaysAgo)}前`) },
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
