import type { Repo } from '../data/model';
import type { Taxonomy } from '../data/taxonomy';
import type { Meta, SchemeInfo, WeeksColumns } from '../data/types';
import type { Store } from '../state/store';

/** 各功能模块共享的上下文。`weeks` 在首屏之后才加载，加载前为 null；`scheme` 与 `taxonomy` 在切换分类体系时更新。 */
export interface Ctx {
  meta: Meta;
  repos: readonly Repo[];
  /** 当前使用的分类体系的简介与目录；没有分类数据（或加载失败）时为 null。切换体系时原地更新。 */
  scheme: SchemeInfo | null;
  taxonomy: Taxonomy | null;
  /** 数据的参照时间（毫秒）。 */
  now: number;
  store: Store;
  weeks: WeeksColumns | null;
}

/** 某项目的周 Star 分布；没有数据或尚未加载时为 null。 */
export function weeksOf(ctx: Ctx, repo: Repo): { start: string; stars: number[] } | null {
  const start = ctx.weeks?.week_start[repo.index];
  const stars = ctx.weeks?.stars[repo.index];
  return start && stars ? { start, stars } : null;
}

const byName = new WeakMap<readonly Repo[], Map<string, Repo>>();

/** 总榜里名为 `name`（忽略大小写）的项目。分类名恰好是项目名时（如 Awesome 清单本身也是总榜里的项目），用它打开该项目的详情。 */
export function repoNamed(ctx: Ctx, name: string): Repo | undefined {
  let index = byName.get(ctx.repos);
  if (!index) byName.set(ctx.repos, (index = new Map(ctx.repos.map((r) => [r.fullName.toLowerCase(), r]))));
  return index.get(name.toLowerCase());
}

/** 项目详情的地址；`name` 不是总榜里的项目时为 null。 */
export function repoHref(ctx: Ctx, name: string): string | null {
  const repo = repoNamed(ctx, name);
  return repo ? `#/${repo.fullName}` : null;
}
