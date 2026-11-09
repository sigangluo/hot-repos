/** 地址与页面状态的对应：`#/trending` 是近期热点，`#/owner/repo` 是项目详情，空地址是总榜。 */

export type View = 'board' | 'trending';

const TRENDING_HASH = '#/trending';

/** 某个视图对应的地址片段（总榜为空）。 */
export function viewHash(view: View): string {
  return view === 'trending' ? TRENDING_HASH : '';
}

export interface Route {
  /** 地址决定的视图；详情地址不指定视图（沿用当前视图），为 null。 */
  view: View | null;
  openRepo: string | null;
}

export function parseHash(hash: string, names: ReadonlySet<string>): Route {
  if (hash === TRENDING_HASH) return { view: 'trending', openRepo: null };
  const match = /^#\/(.+)$/.exec(hash);
  if (!match?.[1]) return { view: 'board', openRepo: null };
  let name: string;
  try {
    name = decodeURIComponent(match[1]);
  } catch {
    return { view: null, openRepo: null };
  }
  return { view: null, openRepo: names.has(name) ? name : null };
}
