import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';

import { loadCore, loadWeeks } from './data/load';
import { asOf, buildRepos } from './data/model';
import type { Ctx } from './features/context';
import { renderDrawer } from './features/drawer';
import { renderFilters } from './features/filters';
import { renderGlossary } from './features/glossary';
import { renderHeader } from './features/header';
import { renderResults } from './features/table';
import { initialScheme, switchScheme } from './features/schemes';
import { renderTrendingPage } from './features/trending';
import { h, mount } from './lib/dom';
import { loadPrefs } from './state/prefs';
import { parseHash } from './state/route';
import { Store } from './state/store';

async function start(app: HTMLElement): Promise<void> {
  mount(app, h('p', { class: 'loading page' }, '正在加载数据…'));
  const [meta, columns] = await loadCore();
  const repos = buildRepos(columns, asOf(meta));
  const store = new Store();
  const ctx: Ctx = { meta, repos, scheme: null, taxonomy: null, now: asOf(meta), store, weeks: null };
  await switchScheme(ctx, initialScheme(meta.schemes, loadPrefs().scheme));

  const drawerHost = h('div', { id: 'drawer-root' });
  const board = h('div', { class: 'layout' }, renderFilters(ctx), renderResults(ctx));
  mount(app, h('main', { class: 'page' },
    renderHeader(ctx),
    renderGlossary(ctx),
    board,
    meta.trending_date ? renderTrendingPage(ctx) : null),
    drawerHost);
  renderDrawer(ctx, drawerHost);
  const showBoard = () => (board.hidden = store.state.view !== 'board');
  store.subscribe((_, changed) => changed.has('view') && showBoard());

  // 地址对应页面状态：`#/trending` 是近期热点，`#/owner/repo` 是项目详情，都可以直接分享。
  const names = new Set(repos.map((r) => r.fullName));
  const sync = () => {
    const route = parseHash(location.hash, names);
    // 没有 Trending 数据时，趋势地址退回总榜。
    const view = route.view === 'trending' && !meta.trending_date ? 'board' : route.view;
    store.set({ ...(view && { view }), openRepo: route.openRepo });
  };
  window.addEventListener('hashchange', sync);
  sync();

  // 周 Star 分布在首屏之后加载，到达后表格的迷你图才出现。
  void loadWeeks().then((weeks) => {
    ctx.weeks = weeks;
    window.dispatchEvent(new Event('hot-repos:weeks'));
  }).catch(() => undefined);
}

const app = document.getElementById('app');
if (app) {
  start(app).catch((error: unknown) => {
    mount(app, h('p', { class: 'error page' }, `页面数据加载失败：${error instanceof Error ? error.message : String(error)}。请先运行 hot-repos export。`));
  });
}
