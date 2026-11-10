import { getScheme } from '../data/schemes';
import { applyScheme } from '../data/model';
import type { SchemeInfo } from '../data/types';
import type { Ctx } from './context';

/** 页面启动时用哪个体系：上次选过且仍存在的，否则列表里的第一个；没有体系为 null。 */
export function initialScheme(schemes: readonly SchemeInfo[], saved: string | null): string | null {
  return (schemes.find((s) => s.id === saved) ?? schemes[0])?.id ?? null;
}

/**
 * 切换分类体系：加载体系文件，把分类应用到全部项目，并清掉依赖旧体系的筛选条件（分类节点、项目形态）。
 * 体系文件加载失败时页面不带分类（与没有分类数据时一样），其余功能不受影响。
 */
export async function switchScheme(ctx: Ctx, id: string | null): Promise<void> {
  const info = ctx.meta.schemes.find((s) => s.id === id) ?? null;
  const data = info ? await getScheme(info.id).catch(() => null) : null;
  applyScheme(ctx.repos, data);
  ctx.scheme = data ? info : null;
  ctx.taxonomy = data?.taxonomy ?? null;
  const { filters } = ctx.store.state;
  const { form: _form, ...selected } = filters.selected;
  ctx.store.set({
    scheme: ctx.scheme?.id ?? null,
    filters: {
      ...filters,
      categories: new Set(),
      // 没有主分类的体系，一个项目的全部分类都算“关联分类”，只有“含关联分类”这一种范围。
      categoryScope: ctx.scheme?.primary === false ? 'all' : 'primary',
      selected,
    },
  });
}
