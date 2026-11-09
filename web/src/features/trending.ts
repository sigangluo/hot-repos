import { loadTrending } from '../data/load';
import type { TrendingFile } from '../data/types';
import { h, mount } from '../lib/dom';
import { dateTime, int } from '../lib/format';
import { ALL_LANGUAGES, PERIODS, buildTrending, type Since, type TrendingItem } from '../state/trending';
import type { Ctx } from './context';

const AVATARS_SHOWN = 5;

/** 项目名既可能是总榜里的项目（打开站内详情），也可能只在 Trending 里（跳到 GitHub）。 */
function nameLink(item: TrendingItem): HTMLAnchorElement {
  const [owner = '', repo = ''] = item.fullName.split('/');
  const label = [h('span', { class: 'owner' }, `${owner} / `), repo];
  return item.boardName
    ? h('a', { class: 'name', href: `#/${item.boardName}` }, label)
    : h('a', { class: 'name external', href: `https://github.com/${item.fullName}`, target: '_blank', rel: 'noopener noreferrer' }, label);
}

function avatars(users: readonly string[]): HTMLElement | null {
  if (users.length === 0) return null;
  return h('span', { class: 'avatars', title: '页面上标注的贡献者' },
    users.slice(0, AVATARS_SHOWN).map((user) => {
      const img = h('img', {
        class: 'avatar', src: `https://github.com/${encodeURIComponent(user)}.png?size=40`,
        alt: `@${user}`, title: `@${user}`, width: 20, height: 20, loading: 'lazy',
      });
      // 机器人等账号没有这个地址的头像，加载失败时直接去掉，不留破图图标。
      img.addEventListener('error', () => img.remove());
      return img;
    }),
  );
}

function entry(item: TrendingItem, periodLabel: string): HTMLElement {
  return h('li', { class: 'trend-item' },
    h('span', { class: 'trend-rank' }, item.rank),
    h('div', { class: 'trend-main' },
      h('div', { class: 'trend-title' },
        nameLink(item),
        item.boardRank != null ? h('span', { class: 'chip plain' }, `总榜第 ${int(item.boardRank)} 名`) : null),
      item.description ? h('p', { class: 'desc' }, item.description) : null,
      h('div', { class: 'trend-meta' },
        item.language ? h('span', null, item.language) : null,
        h('span', { title: 'Star 总数' }, `★ ${int(item.stars)}`),
        h('span', { title: 'Fork 总数' }, `⑂ ${int(item.forks)}`),
        avatars(item.builtBy))),
    h('div', { class: 'trend-gain' }, h('b', null, `+${int(item.periodStars)}`), h('span', null, `${periodLabel}新增 Star`)));
}

/** 近期热点：与 GitHub Trending 对应的时间段和语言筛选，已在总榜中的项目链接到站内详情。 */
export function renderTrending(ctx: Ctx, file: TrendingFile): HTMLElement {
  const model = buildTrending(file, ctx.repos);
  let since: Since = PERIODS[0][0];
  let language = ALL_LANGUAGES;

  const periodButtons = PERIODS.map(([key, label]) =>
    h('button', { type: 'button', dataset: { since: key }, onclick: () => { since = key; draw(); } }, label));
  const select = h('select', { 'aria-label': '编程语言', onchange: () => { language = select.value; draw(); } },
    model.languages.map(([key, label]) => h('option', { value: key }, label)));
  const summary = h('span', { class: 'summary', 'aria-live': 'polite' });
  const listHost = h('div');

  const draw = () => {
    for (const b of periodButtons) b.setAttribute('aria-pressed', String(b.dataset.since === since));
    const label = PERIODS.find(([key]) => key === since)![1];
    const items = model.list(since, language);
    summary.textContent = `共 ${items.length} 个项目`;
    mount(listHost, items.length === 0
      ? h('p', { class: 'empty-state' }, '这个榜单当前没有上榜项目')
      : h('ol', { class: 'trend-list' }, items.map((item) => entry(item, label))));
  };
  draw();

  return h('section', { class: 'trending', 'aria-label': '近期热点' },
    h('div', { class: 'toolbar trend-controls' },
      h('span', { class: 'seg', role: 'group', 'aria-label': '时间段' }, periodButtons),
      select,
      summary),
    h('p', { class: 'trend-note' },
      `GitHub Trending 页面在 ${file.snapshot_date} 的快照（抓取于 ${dateTime(file.captured_at * 1000)}），每天更新一次；榜单条数由 GitHub 决定，不固定。`),
    listHost);
}

/**
 * 近期热点页面：第一次切换到该视图时才加载数据；加载失败可以重试。
 * `load` 可替换，便于测试。
 */
export function renderTrendingPage(ctx: Ctx, load: () => Promise<TrendingFile> = loadTrending): HTMLElement {
  const host = h('div', { class: 'trending-page' });
  let started = false;

  const start = () => {
    mount(host, h('p', { class: 'loading' }, '正在加载近期热点…'));
    load().then(
      (file) => mount(host, renderTrending(ctx, file)),
      (error: unknown) => mount(host, h('div', { class: 'empty-state' },
        h('p', { class: 'error' }, `近期热点加载失败：${error instanceof Error ? error.message : String(error)}`),
        h('button', { type: 'button', class: 'btn', onclick: start }, '重试'))),
    );
  };
  const sync = () => {
    const visible = ctx.store.state.view === 'trending';
    host.hidden = !visible;
    if (visible && !started) {
      started = true;
      start();
    }
  };
  sync();
  ctx.store.subscribe((_, changed) => changed.has('view') && sync());
  return host;
}
