import type { Repo } from '../data/model';
import type { TrendingFile } from '../data/types';

/** Trending 的三个时间段：键与数据一致，后面是新增 Star 的称呼。 */
export const PERIODS = [
  ['daily', '今日'],
  ['weekly', '本周'],
  ['monthly', '本月'],
] as const;

export type Since = (typeof PERIODS)[number][0];

export const ALL_LANGUAGES = 'all';

export interface TrendingItem {
  rank: number;
  fullName: string;
  description: string | null;
  language: string | null;
  stars: number;
  forks: number;
  /** 该时间段新增的 Star（页面显示的数字）。 */
  periodStars: number;
  builtBy: readonly string[];
  /** 项目在总榜中的名次；不在总榜（Top N 之外）时为 null。 */
  boardRank: number | null;
  /** 在总榜时的项目名（用大小写与总榜一致的写法打开详情）；否则为 null。 */
  boardName: string | null;
}

export interface TrendingModel {
  /** [键, 显示名]，“全部语言”在前。 */
  languages: readonly [string, string][];
  /** 某个（时间段，语言）的榜单，按页面顺序；没有上榜项目时为空数组。 */
  list(since: string, language: string): readonly TrendingItem[];
}

/** 把列式的快照整理成按（时间段，语言）分组的榜单，并标出已在总榜中的项目。 */
export function buildTrending(file: TrendingFile, repos: readonly Repo[]): TrendingModel {
  const board = new Map(repos.map((r) => [r.fullName.toLowerCase(), r]));
  const groups = new Map<string, TrendingItem[]>();
  const c = file.rows;
  for (let i = 0; i < c.rank.length; i++) {
    const inBoard = board.get(c.full_name[i]!.toLowerCase());
    const item: TrendingItem = {
      rank: c.rank[i]!,
      fullName: c.full_name[i]!,
      description: c.description[i] ?? null,
      language: c.repo_language[i] ?? null,
      stars: c.stars[i]!,
      forks: c.forks[i]!,
      periodStars: c.period_stars[i]!,
      builtBy: c.built_by[i] ?? [],
      boardRank: inBoard?.rank ?? null,
      boardName: inBoard?.fullName ?? null,
    };
    const key = `${c.since[i]}|${c.language[i]}`;
    const group = groups.get(key);
    if (group) group.push(item);
    else groups.set(key, [item]);
  }
  for (const group of groups.values()) group.sort((a, b) => a.rank - b.rank);
  return { languages: file.languages, list: (since, language) => groups.get(`${since}|${language}`) ?? [] };
}
