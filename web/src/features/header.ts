import { DATA_TIMES, STALE_HOURS } from '../data/glossary';
import { h, mount } from '../lib/dom';
import { ago, dateTime, int } from '../lib/format';
import { applyTheme } from '../lib/theme';
import type { Theme } from '../state/prefs';
import { viewHash, type View } from '../state/route';
import type { Ctx } from './context';

const THEMES: [Theme, string][] = [
  ['auto', '跟随系统'],
  ['light', '浅色'],
  ['dark', '深色'],
];

const VIEWS: [View, string][] = [
  ['board', '总榜'],
  ['trending', '近期热点'],
];

export function renderHeader(ctx: Ctx): HTMLElement {
  const { meta, store } = ctx;
  const themeButtons = THEMES.map(([theme, label]) =>
    h('button', { type: 'button', onclick: () => store.set({ theme }), dataset: { theme } }, label),
  );
  const syncTheme = () => {
    for (const b of themeButtons) b.setAttribute('aria-pressed', String(b.dataset.theme === store.state.theme));
    applyTheme(store.state.theme);
  };
  syncTheme();
  store.subscribe((_, changed) => changed.has('theme') && syncTheme());

  const fetched = meta.repos_fetched_at;
  const stale = fetched != null && Date.now() - fetched[1] * 1000 > STALE_HOURS * 3_600_000;
  const range = (value: [number, number] | null) =>
    value == null
      ? '—'
      : value[0] === value[1]
        ? dateTime(value[0] * 1000)
        : `${dateTime(value[0] * 1000)} ~ ${dateTime(value[1] * 1000)}`;
  const definitions = new Map(DATA_TIMES);
  const item = (label: string, value: string) =>
    h('span', { title: definitions.get(label) }, `${label} `, h('b', null, value));

  const fresh = h(
    'div',
    { class: stale ? 'fresh stale' : 'fresh', 'aria-label': '数据新鲜度' },
    item('快照日期', meta.snapshot_date),
    item('总榜采集', dateTime(meta.rank_captured_at * 1000)),
    item('元数据获取', range(fetched)),
    item('周 Star 分布获取', range(meta.star_weeks_fetched_at)),
    stale && fetched ? h('span', null, `数据已 ${ago(fetched[1] * 1000)}，建议重新采集`) : null,
  );

  const subtitle = h('p');
  const header = h(
    'header',
    { class: 'top' },
    h('div', null, h('h1', null, 'GitHub 热门项目看板'), subtitle),
    h('span', { class: 'seg', role: 'group', 'aria-label': '主题' }, themeButtons),
  );

  // 没有 Trending 快照时只有总榜，不显示视图切换。
  const viewButtons = VIEWS.map(([view, label]) =>
    h('button', {
      type: 'button',
      dataset: { view },
      onclick: () => {
        if (store.state.view === view) return;
        history.pushState(null, '', location.pathname + location.search + viewHash(view));
        store.set({ view });
      },
    }, label),
  );
  const views = meta.trending_date
    ? h('nav', { class: 'views', 'aria-label': '视图' }, h('span', { class: 'seg', role: 'group' }, viewButtons))
    : null;

  const syncView = () => {
    const { view } = store.state;
    for (const b of viewButtons) b.setAttribute('aria-pressed', String(b.dataset.view === view));
    subtitle.textContent =
      view === 'trending'
        ? `GitHub Trending 每日快照，最新一期 ${meta.trending_date ?? ''}`
        : `总 Star 榜 Top ${int(meta.board_size)}，共收录 ${int(meta.repos)} 个项目`;
    fresh.hidden = view === 'trending';
  };
  syncView();
  store.subscribe((_, changed) => changed.has('view') && syncView());

  const root = h('div');
  mount(root, header, views, fresh);
  return root;
}
