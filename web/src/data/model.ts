import { buildTaxonomy } from './taxonomy';
import type { ClassificationFile, Meta, RepoColumns } from './types';

const DAY = 86_400_000;

export const NO_LANGUAGE = '未返回主语言';
export const NO_LICENSE = '未声明';

export type LicenseClass = '宽松' | 'Copyleft' | '其他' | typeof NO_LICENSE;

const PERMISSIVE = new Set([
  'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC', 'Unlicense', 'CC0-1.0', '0BSD', 'Zlib',
]);
const COPYLEFT_PREFIX = ['GPL', 'AGPL', 'LGPL', 'MPL', 'EPL', 'EUPL', 'OSL', 'CC-BY-SA'];

/** 许可证类别的含义，供筛选和“名词与口径说明”使用。 */
export const LICENSE_DEFINITIONS: Record<LicenseClass, string> = {
  宽松: 'MIT、Apache-2.0、BSD、ISC 等，对再分发的限制较少。',
  Copyleft: 'GPL、AGPL、LGPL、MPL 等，再分发修改后的版本时通常要求沿用相同许可。',
  其他: '已识别、但不属于以上两类，如 NOASSERTION（识别到许可证文件但无法确定类型）、CC-BY 等。',
  [NO_LICENSE]: '没有识别出许可证；没有许可证时，他人使用和再分发的权利不明确。',
};

export function licenseClass(spdx: string | null): LicenseClass {
  if (!spdx) return NO_LICENSE;
  if (PERMISSIVE.has(spdx)) return '宽松';
  if (COPYLEFT_PREFIX.some((p) => spdx.startsWith(p))) return 'Copyleft';
  return '其他';
}

/** 表格、筛选、搜索使用的一行。`index` 是它在数据文件中的行号，用于对齐 details / weeks。 */
export interface Repo {
  index: number;
  rank: number;
  fullName: string;
  owner: string;
  name: string;
  description: string | null;
  isOrg: boolean;
  createdAt: number;
  pushedAt: number | null;
  archived: boolean;
  fork: boolean;
  template: boolean;
  stars: number;
  forks: number;
  watchers: number;
  openIssues: number;
  closedIssues: number;
  openPrs: number;
  mergedPrs: number;
  discussions: number;
  language: string;
  topics: string[];
  license: string | null;
  licenseClass: LicenseClass;
  commits: number | null;
  contributors: number | null;
  releases: number;
  latestReleaseAt: number | null;
  diskKb: number | null;
  hasHomepage: boolean;
  hasFunding: boolean;
  hasReadme: boolean;
  /** 创建至今的天数（以数据获取时间为准）。 */
  ageDays: number;
  /** 距最近一次推送的天数；没有推送记录为 null。 */
  pushedDaysAgo: number | null;
  /** 主分类路径，从一级到最具体的一级；未分类为空数组。 */
  category: string[];
  /** 关联分类路径（项目同时属于的其他分类）。 */
  relatedPaths: string[][];
  /** 主分类路径上的全部节点（目录下标，含各级父节点）：选中其中任一节点，该项目都算在它之下。 */
  categoryNodes: number[];
  /** 关联分类路径上的全部节点（去重）。 */
  relatedNodes: number[];
  /** 项目形态（应用、库、教程……），可多个。 */
  forms: string[];
  /** 小写的搜索文本：名称、描述、话题、语言、分类。 */
  haystack: string;
}

/** 数据的参照时间：元数据获取时间的最大值，使页面上的“多久以前”不随打开时间漂移。 */
export function asOf(meta: Meta): number {
  return (meta.repos_fetched_at?.[1] ?? meta.rank_captured_at) * 1000;
}

const unique = <T>(values: T[]): T[] => [...new Set(values)];

const ms = (seconds: number | null): number | null => (seconds == null ? null : seconds * 1000);

export function buildRepos(c: RepoColumns, now: number, classification: ClassificationFile | null = null): Repo[] {
  const taxonomy = classification && buildTaxonomy(classification);
  return c.full_name.map((fullName, i): Repo => {
    const [owner = '', name = ''] = fullName.split('/');
    const description = c.description[i] ?? null;
    const topics = c.topics[i] ?? [];
    const language = c.primary_language[i] ?? NO_LANGUAGE;
    const license = c.license[i] ?? null;
    const createdAt = (c.created_at[i] ?? 0) * 1000;
    const pushedAt = ms(c.pushed_at[i] ?? null);
    const primary = classification?.category[i] ?? null;
    const category = taxonomy && primary != null ? taxonomy.path(primary) : [];
    const relatedPaths = taxonomy ? (classification?.related[i] ?? []).map((n) => taxonomy.path(n)) : [];
    const paths = category.length ? [category, ...relatedPaths] : [];
    const related = classification?.related[i] ?? [];
    const forms = taxonomy ? (classification?.form[i] ?? []).map((f) => taxonomy.formLabel(f)) : [];
    return {
      index: i,
      rank: c.rank[i] ?? 0,
      fullName,
      owner,
      name,
      description,
      isOrg: c.owner_type[i] === 'Organization',
      createdAt,
      pushedAt,
      archived: c.is_archived[i] ?? false,
      fork: c.is_fork[i] ?? false,
      template: c.is_template[i] ?? false,
      stars: c.stars[i] ?? 0,
      forks: c.forks[i] ?? 0,
      watchers: c.watchers[i] ?? 0,
      openIssues: c.open_issues[i] ?? 0,
      closedIssues: c.closed_issues[i] ?? 0,
      openPrs: c.open_prs[i] ?? 0,
      mergedPrs: c.merged_prs[i] ?? 0,
      discussions: c.discussions[i] ?? 0,
      language,
      topics,
      license,
      licenseClass: licenseClass(license),
      commits: c.commit_count[i] ?? null,
      contributors: c.contributors[i] ?? null,
      releases: c.release_count[i] ?? 0,
      latestReleaseAt: ms(c.latest_release_at[i] ?? null),
      diskKb: c.disk_usage_kb[i] ?? null,
      hasHomepage: c.has_homepage[i] ?? false,
      hasFunding: c.has_funding[i] ?? false,
      hasReadme: c.has_readme[i] ?? false,
      ageDays: Math.max(0, (now - createdAt) / DAY),
      pushedDaysAgo: pushedAt == null ? null : Math.max(0, (now - pushedAt) / DAY),
      category,
      relatedPaths,
      categoryNodes: taxonomy && primary != null ? taxonomy.pathNodes(primary) : [],
      relatedNodes: taxonomy ? unique(related.flatMap((n) => taxonomy.pathNodes(n))) : [],
      forms,
      haystack: [fullName, description ?? '', topics.join(' '), language, ...paths.flat(), ...forms]
        .join('\n')
        .toLowerCase(),
    };
  });
}
