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
