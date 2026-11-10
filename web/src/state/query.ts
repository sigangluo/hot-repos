import { LICENSE_DEFINITIONS, type Repo } from '../data/model';
import type { Taxonomy } from '../data/taxonomy';

// ───────────────────────── 筛选 ─────────────────────────
// 全部为纯函数：输入数据与条件，输出结果，不碰 DOM，便于测试。

/** 分类筛选组：一个项目在该组里有一个或多个取值，选中的取值满足任一（或全部）即通过。 */
export interface Group {
  id: string;
  label: string;
  values: (r: Repo) => string[];
  /** 选项展示顺序；缺省按项目数降序。 */
  order?: readonly string[];
  /** 是否提供“满足全部”模式（仅话题这类多值组有意义）。 */
  allowAll?: boolean;
  /** 选项太多时只展示前若干个，其余通过搜索选择。 */
  limit?: number;
  /** 该分组在当前数据中是否可用；缺省总是可用。不可用的分组不显示。 */
  available?: (repos: readonly Repo[]) => boolean;
  /** 这一组筛选的是什么、怎么算的。每个分组都必须写，页面在分组标题下显示。 */
  definition: string;
  /** 各选项的含义，选项名为键；可以依赖分类目录。有则显示“各选项说明”。 */
  optionDefinitions?: Record<string, string> | ((taxonomy: Taxonomy | null) => Record<string, string>);
}

const PUSH_BUCKETS = ['7 天内', '30 天内', '90 天内', '1 年内', '超过 1 年', '无推送记录'] as const;
const AGE_BUCKETS = ['不足 1 年', '1–3 年', '3–5 年', '5–10 年', '10 年以上'] as const;
const FEATURES = ['有主页', '有赞助链接', '有 README', '有讨论帖', '有发布版本'] as const;
const LICENSES = ['宽松', 'Copyleft', '其他', '未声明'] as const;

export function pushBucket(days: number | null): (typeof PUSH_BUCKETS)[number] {
  if (days == null) return '无推送记录';
  if (days <= 7) return '7 天内';
  if (days <= 30) return '30 天内';
  if (days <= 90) return '90 天内';
  if (days <= 365) return '1 年内';
  return '超过 1 年';
}

export function ageBucket(days: number): (typeof AGE_BUCKETS)[number] {
  const years = days / 365.25;
  if (years < 1) return '不足 1 年';
  if (years < 3) return '1–3 年';
  if (years < 5) return '3–5 年';
  if (years < 10) return '5–10 年';
  return '10 年以上';
}

/** 当前分类体系里有项目带形态（没有分类，或体系没有形态时没有）。 */
export const hasForms = (repos: readonly Repo[]) => repos.some((r) => r.forms.length > 0);

export const GROUPS: readonly Group[] = [
  {
    id: 'form',
    label: '项目形态',
    values: (r) => r.forms,
    available: hasForms,
    definition: '项目是什么样的东西（应用、库、智能体技能……），与“分类”（它服务于什么领域）相互独立；一个项目可以有多个形态。',
    optionDefinitions: (taxonomy) => Object.fromEntries((taxonomy?.forms ?? []).map((f) => [f.label, f.definition])),
  },
  {
    id: 'language',
    label: '主要语言',
    values: (r) => [r.language],
    limit: 15,
    definition: 'GitHub 判定的主要语言，即代码字节数最多的语言。没有识别出语言的项目归入“未返回主语言”。',
  },
  {
    id: 'license',
    label: '许可证',
    values: (r) => [r.licenseClass],
    order: LICENSES,
    definition: '按许可证类型粗分，依据 GitHub 识别出的许可证标识。仅供筛选参考，不构成法律意见；具体权利以许可证原文为准。',
    optionDefinitions: LICENSE_DEFINITIONS,
  },
  {
    id: 'topic',
    label: '话题',
    values: (r) => r.topics,
    allowAll: true,
    limit: 20,
    definition: '仓库作者自己填写的话题标签，不是统一的分类，同一件事可能有不同写法。可选“满足任一”或“满足全部”。',
  },
  {
    id: 'owner',
    label: '所有者',
    values: (r) => [r.isOrg ? '组织' : '个人'],
    order: ['组织', '个人'],
    definition: '仓库属于组织账号还是个人账号。',
  },
  {
    id: 'pushed',
    label: '最近推送',
    values: (r) => [pushBucket(r.pushedDaysAgo)],
    order: PUSH_BUCKETS,
    definition: '距最近一次向仓库推送代码的时间，以数据获取时间为参照（不随你打开页面的时间变化）。“无推送记录”是 GitHub 没有返回推送时间。',
  },
  {
    id: 'age',
    label: '创建时长',
    values: (r) => [ageBucket(r.ageDays)],
    order: AGE_BUCKETS,
    definition: '距仓库在 GitHub 上创建的时间，以数据获取时间为参照。仓库可能是后来才迁移或公开的，创建时间不等于项目的真实年龄。',
  },
  {
    id: 'archived',
    label: '归档状态',
    values: (r) => [r.archived ? '已归档' : '未归档'],
    order: ['未归档', '已归档'],
    definition: '已归档的仓库被作者设为只读，通常不再维护。',
  },
  {
    id: 'feature',
    label: '资料与功能',
    definition: '仓库具备哪些资料或功能，可多选；多选时满足任一即可。',
    optionDefinitions: {
      有主页: '仓库填写了项目主页地址。',
      有赞助链接: '仓库配置了赞助（Sponsor）入口。',
      '有 README': '仓库根目录有 Markdown 格式的 README。',
      有讨论帖: '讨论区里至少有一个讨论帖。',
      有发布版本: 'GitHub 上至少有一次 Release。',
    },
    order: FEATURES,
    values: (r) =>
      [
        r.hasHomepage && '有主页',
        r.hasFunding && '有赞助链接',
        r.hasReadme && '有 README',
        r.discussions > 0 && '有讨论帖',
        r.releases > 0 && '有发布版本',
      ].filter((x): x is string => typeof x === 'string'),
  },
];

export interface Range {
  min: number | null;
  max: number | null;
}

/** 分类筛选按哪些分类计算：只看主分类，或同时包含关联分类。 */
export type CategoryScope = 'primary' | 'all';

export interface Filters {
  text: string;
  /** 选中的分类节点（目录下标，任意一级）：项目在其下（含子分类）即通过。 */
  categories: ReadonlySet<number>;
  categoryScope: CategoryScope;
  /** 每个分组选中的取值。 */
  selected: Record<string, ReadonlySet<string>>;
  /** 多值分组（话题）的匹配方式。 */
  matchAll: Record<string, boolean>;
  stars: Range;
  contributors: Range;
}

export function emptyFilters(): Filters {
  return {
    text: '',
    categories: new Set(),
    categoryScope: 'primary',
    selected: {},
    matchAll: {},
    stars: { min: null, max: null },
    contributors: { min: null, max: null },
  };
}

function inRange(value: number | null, range: Range): boolean {
  if (range.min == null && range.max == null) return true;
  if (value == null) return false;
  return (range.min == null || value >= range.min) && (range.max == null || value <= range.max);
}

/** 项目在分类树上占据的节点（含各级父节点）。 */
function categoryNodes(repo: Repo, scope: CategoryScope): readonly number[] {
  return scope === 'all' ? [...repo.categoryNodes, ...repo.relatedNodes] : repo.categoryNodes;
}

function matchesCategories(repo: Repo, filters: Filters): boolean {
  return filters.categories.size === 0 || categoryNodes(repo, filters.categoryScope).some((n) => filters.categories.has(n));
}

function matchesGroup(repo: Repo, group: Group, filters: Filters): boolean {
  const chosen = filters.selected[group.id];
  if (!chosen || chosen.size === 0) return true;
  const values = group.values(repo);
  return filters.matchAll[group.id]
    ? [...chosen].every((v) => values.includes(v))
    : values.some((v) => chosen.has(v));
}

/** 判断项目是否满足条件；`except` 指定的分组（分类树用 `CATEGORY_GROUP`）不参与判断，用于计算该分组各选项的数量。 */
export function matches(repo: Repo, filters: Filters, except?: string): boolean {
  const text = filters.text.trim().toLowerCase();
  if (text && !text.split(/\s+/).every((word) => repo.haystack.includes(word))) return false;
  if (!inRange(repo.stars, filters.stars) || !inRange(repo.contributors, filters.contributors)) return false;
  if (except !== CATEGORY_GROUP && !matchesCategories(repo, filters)) return false;
  return GROUPS.every((g) => g.id === except || matchesGroup(repo, g, filters));
}

export const CATEGORY_GROUP = 'category';

/** 分类树各节点在“满足其他全部条件”时的项目数（节点含其子分类下的项目，每个项目在每个节点只计一次）。 */
export function categoryCounts(repos: readonly Repo[], filters: Filters): Map<number, number> {
  const counts = new Map<number, number>();
  for (const repo of repos) {
    if (!matches(repo, filters, CATEGORY_GROUP)) continue;
    for (const node of new Set(categoryNodes(repo, filters.categoryScope))) counts.set(node, (counts.get(node) ?? 0) + 1);
  }
  return counts;
}

export function applyFilters(repos: readonly Repo[], filters: Filters): Repo[] {
  return repos.filter((r) => matches(r, filters));
}

/** 某分组各选项在“满足其他全部条件”时的项目数。已选中但数量为 0 的选项仍保留，便于取消。 */
export function facetCounts(repos: readonly Repo[], filters: Filters, group: Group): [string, number][] {
  const counts = new Map<string, number>();
  for (const repo of repos) {
    if (!matches(repo, filters, group.id)) continue;
    for (const value of group.values(repo)) counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  for (const value of filters.selected[group.id] ?? []) if (!counts.has(value)) counts.set(value, 0);
  const rank = (v: string) => group.order?.indexOf(v) ?? -1;
  return [...counts].sort(([a, na], [b, nb]) =>
    group.order ? rank(a) - rank(b) : nb - na || a.localeCompare(b),
  );
}

export function activeCount(filters: Filters): number {
  const groups = Object.values(filters.selected).reduce((n, set) => n + set.size, 0) + filters.categories.size;
  const ranges = [filters.stars, filters.contributors].filter((r) => r.min != null || r.max != null).length;
  return groups + ranges + (filters.text.trim() ? 1 : 0);
}

// ───────────────────────── 排序与分页 ─────────────────────────

export type SortDirection = 'asc' | 'desc';

/** 按取值排序；缺失值（null）始终排在最后，不受方向影响。相同时按名次，保证结果稳定。 */
export function sortRepos<T extends string>(
  repos: readonly Repo[],
  value: (r: Repo, key: T) => number | string | null,
  key: T,
  direction: SortDirection,
): Repo[] {
  const sign = direction === 'asc' ? 1 : -1;
  return [...repos].sort((a, b) => {
    const x = value(a, key);
    const y = value(b, key);
    if (x == null && y == null) return a.rank - b.rank;
    if (x == null) return 1;
    if (y == null) return -1;
    const order = typeof x === 'string' && typeof y === 'string' ? x.localeCompare(y) : Number(x) - Number(y);
    return order * sign || a.rank - b.rank;
  });
}

export interface Page<T> {
  items: T[];
  page: number;
  pages: number;
  total: number;
}

/** 分页；页码越界时修正到有效范围。 */
export function paginate<T>(items: readonly T[], page: number, pageSize: number): Page<T> {
  const pages = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.min(Math.max(1, page), pages);
  return {
    items: items.slice((current - 1) * pageSize, current * pageSize),
    page: current,
    pages,
    total: items.length,
  };
}
