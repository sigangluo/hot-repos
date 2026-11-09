import { createStarChart, type ChartMode, type StarChart } from '../charts/star-chart';
import type { Repo } from '../data/model';
import { loadDetails, loadWeeks } from '../data/load';
import type { DetailColumns } from '../data/types';
import { h, mount } from '../lib/dom';
import { ageText, compact, date, dateTime, int } from '../lib/format';
import { viewHash } from '../state/route';
import { weeksOf, type Ctx } from './context';
import { POSITION_METRICS, metricPosition, metricValues, type Position } from './position';
import { loadReadme } from './readme';

const LANGUAGE_SLOTS = 7;

export function closeDrawer(ctx: Ctx): void {
  history.pushState(null, '', location.pathname + location.search + viewHash(ctx.store.state.view));
  ctx.store.set({ openRepo: null });
}

export function renderDrawer(ctx: Ctx, host: HTMLElement): void {
  const { store, repos } = ctx;
  const byName = new Map(repos.map((r) => [r.fullName, r]));
  let teardown: (() => void) | null = null;

  const close = () => {
    teardown?.();
    teardown = null;
    mount(host);
  };

  store.subscribe((state, changed) => {
    if (!changed.has('openRepo')) return;
    close();
    const repo = state.openRepo ? byName.get(state.openRepo) : undefined;
    if (repo) teardown = open(ctx, repo, host);
  });
}

function open(ctx: Ctx, repo: Repo, host: HTMLElement): () => void {
  const abort = new AbortController();
  const previousFocus = document.activeElement as HTMLElement | null;
  let chart: StarChart | null = null;
  let disposed = false;

  const overview = h('div', { class: 'drawer-body', role: 'tabpanel' });
  const readme = h('div', { class: 'drawer-body', role: 'tabpanel', hidden: true });
  const tabButtons = [
    h('button', { type: 'button', role: 'tab', 'aria-selected': 'true' }, '概览'),
    h('button', { type: 'button', role: 'tab', 'aria-selected': 'false' }, 'README'),
  ];
  let readmeStarted = false;
  const select = (index: number) => {
    tabButtons.forEach((b, i) => b.setAttribute('aria-selected', String(i === index)));
    overview.hidden = index !== 0;
    readme.hidden = index !== 1;
    if (index === 1 && !readmeStarted) {
      readmeStarted = true;
      void fillReadme(readme, repo, abort.signal);
    }
  };
  tabButtons.forEach((b, i) => b.addEventListener('click', () => select(i)));

  const closeButton = h('button', { type: 'button', class: 'btn', 'aria-label': '关闭详情', onclick: () => closeDrawer(ctx) }, '关闭');
  const drawer = h('aside', { class: 'drawer', role: 'dialog', 'aria-modal': 'true', 'aria-label': repo.fullName },
    h('div', { class: 'drawer-head' },
      h('div', null,
        h('h2', null, h('a', { href: `https://github.com/${repo.fullName}`, target: '_blank', rel: 'noopener noreferrer' }, repo.fullName)),
        h('p', null, repo.description ?? '没有描述')),
      closeButton),
    h('div', { class: 'tabs', role: 'tablist' }, tabButtons),
    overview,
    readme);
  const overlay = h('div', { class: 'overlay', onclick: () => closeDrawer(ctx) });
  mount(host, overlay, drawer);
  closeButton.focus();

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') closeDrawer(ctx);
    if (e.key !== 'Tab') return;
    // 焦点限制在抽屉内。
    const items = [...drawer.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, select')].filter((el) => el.offsetParent !== null);
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { last?.focus(); e.preventDefault(); }
    else if (!e.shiftKey && document.activeElement === last) { first?.focus(); e.preventDefault(); }
  };
  document.addEventListener('keydown', onKey);
  const onTheme = () => chart?.restyle();
  const unsubscribe = ctx.store.subscribe((_, changed) => changed.has('theme') && onTheme());
  const media = matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', onTheme);

  void fillOverview(ctx, overview, repo, (c) => {
    if (disposed) c.dispose();
    else chart = c;
  });

  return () => {
    disposed = true;
    unsubscribe();
    abort.abort();
    chart?.dispose();
    document.removeEventListener('keydown', onKey);
    media.removeEventListener('change', onTheme);
    previousFocus?.focus();
  };
}

function fact(label: string, value: string | Node | null) {
  return h('div', null, h('dt', null, label), h('dd', null, value ?? '—'));
}

async function fillOverview(ctx: Ctx, el: HTMLElement, repo: Repo, onChart: (c: StarChart) => void): Promise<void> {
  const facts = h('dl', { class: 'facts' },
    fact('Star', int(repo.stars)), fact('Fork', int(repo.forks)), fact('Watch', int(repo.watchers)),
    fact('贡献者', int(repo.contributors)), fact('提交数', int(repo.commits)),
    fact('Issue', `${int(repo.openIssues)} 未关 / ${int(repo.closedIssues)} 已关`),
    fact('Pull Request', `${int(repo.openPrs)} 未合 / ${int(repo.mergedPrs)} 已合`),
    fact('发布', repo.releases ? `${int(repo.releases)} 个，最近 ${date(repo.latestReleaseAt)}` : '无'),
    fact('创建', `${date(repo.createdAt)}（${ageText(repo.ageDays)}）`),
    fact('最近推送', repo.pushedAt == null ? '—' : `${date(repo.pushedAt)}（${ageText(repo.pushedDaysAgo)}前）`),
    fact('主要语言', repo.language), fact('许可证', repo.license ?? '未声明'),
    fact('所有者', repo.isOrg ? '组织' : '个人'),
    fact('状态', [repo.archived && '已归档', repo.fork && 'Fork', repo.template && '模板'].filter(Boolean).join('、') || '正常'),
    fact('代码体积', repo.diskKb == null ? '—' : `${compact(repo.diskKb)} KB`),
  );
  const chartHost = h('div', { class: 'loading' }, '正在加载周 Star 分布…');
  const langHost = h('div', { class: 'loading' }, '正在加载详情…');
  const linksHost = h('div', { class: 'chips' });
  mount(el,
    h('section', { class: 'card' }, h('h3', null, '基本信息'), facts),
    positionCard(ctx, repo),
    h('section', { class: 'card' }, h('h3', null, '官方周 Star 分布'), chartHost),
    h('section', { class: 'card' }, h('h3', null, '语言构成'), langHost),
    repo.topics.length
      ? h('section', { class: 'card' }, h('h3', null, '话题'), h('div', { class: 'chips' }, repo.topics.map((t) => h('span', { class: 'chip plain' }, t))))
      : null,
    h('section', { class: 'card' }, h('h3', null, '链接'), linksHost));

  const [weeksResult, detailsResult] = await Promise.allSettled([loadWeeks(), loadDetails()]);
  if (!el.isConnected) return;

  if (weeksResult.status === 'fulfilled') {
    ctx.weeks = weeksResult.value;
    const weeks = weeksOf(ctx, repo);
    const details = detailsResult.status === 'fulfilled' ? detailsResult.value : null;
    if (!weeks) mount(chartHost, h('p', { class: 'muted' }, '该项目没有周 Star 数据。'));
    else await drawChart(chartHost, weeks, details, repo.index, onChart);
  } else mount(chartHost, h('p', { class: 'error' }, '周 Star 数据加载失败。'));

  if (detailsResult.status === 'fulfilled') {
    const d = detailsResult.value;
    mount(langHost, languageBar(d.languages[repo.index] ?? []));
    mount(linksHost, ...links(repo, d));
  } else {
    mount(langHost, h('p', { class: 'error' }, '详情数据加载失败。'));
  }
}

let positionValues: Map<string, number[]> | null = null;

/** 项目在完整总榜（不受筛选影响）各项指标上的位置。 */
function positionCard(ctx: Ctx, repo: Repo): Node {
  const values = (positionValues ??= metricValues(ctx.repos));
  const rows = POSITION_METRICS.map((metric) => {
    const value = metric.value(repo);
    const all = values.get(metric.label) ?? [];
    const position = value == null ? null : metricPosition(all, value);
    return h('div', { class: 'pos-row' },
      h('span', null, metric.label),
      position ? positionTrack(all, position) : h('span', { class: 'muted' }, '无数据'),
      h('span', { class: 'pos-text' }, position ? `第 ${int(position.rank)} 名 / ${int(position.total)}` : ''));
  });
  return h('section', { class: 'card' },
    h('h3', null, '在总榜中的位置'),
    h('div', { class: 'pos' }, rows),
    h('p', { class: 'note' }, '以完整总榜为参照，不受当前筛选影响；圆点为该项目，竖线为中位数。位置按对数刻度从最小值排到最大值，并非百分位。名次 1 表示数值最大。'));
}

function positionTrack(all: readonly number[], p: Position): Node {
  const median = metricPosition(all, p.median)?.fraction ?? 0.5;
  const text = `${int(p.value)}（最小 ${int(p.min)}，中位数 ${int(p.median)}，最大 ${int(p.max)}）`;
  return h('div', { class: 'track', role: 'img', 'aria-label': text, title: text },
    h('i', { class: 'tick', style: `left:${(median * 100).toFixed(2)}%` }),
    h('i', { class: 'dot', style: `left:${(p.fraction * 100).toFixed(2)}%` }));
}

async function drawChart(host: HTMLElement, weeks: { start: string; stars: number[] }, details: DetailColumns | null, index: number, onChart: (c: StarChart) => void) {
  const fetched = details?.star_weeks_pages_fetched[index];
  const total = details?.star_weeks_pages_total[index];
  const partial = fetched != null && total != null && fetched < total;
  const first = weeks.start;
  const last = weekLabelsEnd(weeks);
  const canvas = h('div', { class: 'chart' });
  let mode: ChartMode = 'weekly';
  let chart: StarChart | null = null;
  const buttons = (['weekly', 'cumulative'] as const).map((m) =>
    h('button', { type: 'button', 'aria-pressed': String(m === mode), onclick: () => {
      mode = m;
      buttons.forEach((b, i) => b.setAttribute('aria-pressed', String((['weekly', 'cumulative'] as const)[i] === mode)));
      chart?.setMode(mode);
    } }, m === 'weekly' ? '按周' : '已收录时段累计'));
  mount(host,
    h('div', { class: 'seg', role: 'group', 'aria-label': '图表模式' }, buttons),
    canvas,
    h('p', { class: 'note' }, `${first} 至 ${last}，共 ${weeks.stars.length} 周。统计采集时仍保留的 Star 按创建时间的分布，已取消的 Star 不在其中；“累计”只是已收录时段内的累加，不是历史净增长。${partial ? `仅抓取了最近 ${fetched} / ${total} 页。` : ''}`));
  chart = await createStarChart(canvas, weeks.start, weeks.stars, mode);
  onChart(chart);
}

function weekLabelsEnd(weeks: { start: string; stars: number[] }): string {
  return new Date(Date.parse(`${weeks.start}T00:00:00Z`) + (weeks.stars.length - 1) * 7 * 86_400_000).toISOString().slice(0, 10);
}

function languageBar(languages: [string, number][]): Node {
  const total = languages.reduce((n, [, bytes]) => n + bytes, 0);
  if (total === 0) return h('p', { class: 'muted' }, '没有语言构成数据。');
  const head = languages.slice(0, LANGUAGE_SLOTS);
  const rest = languages.slice(LANGUAGE_SLOTS).reduce((n, [, bytes]) => n + bytes, 0);
  const parts: [string, number, string][] = head.map(([name, bytes], i) => [name, bytes, `var(--cat-${i + 1})`]);
  if (rest > 0) parts.push(['其他', rest, 'var(--cat-other)']);
  return h('div', { class: 'card', style: 'border:0;padding:0' },
    h('div', { class: 'langbar', role: 'img', 'aria-label': parts.map(([n, b]) => `${n} ${(b / total * 100).toFixed(1)}%`).join('，') },
      parts.map(([name, bytes, color]) => h('span', { title: name, style: `width:${(bytes / total) * 100}%;background:${color}` }))),
    h('div', { class: 'legend' }, parts.map(([name, bytes, color]) =>
      h('span', null, h('i', { style: `background:${color}` }), `${name} ${(bytes / total * 100).toFixed(1)}%`))),
    h('p', { class: 'note' }, '按代码字节数统计，仅包含字节数最多的前 10 种语言。'));
}

function links(repo: Repo, d: DetailColumns): Node[] {
  const out: Node[] = [h('a', { class: 'chip', href: `https://github.com/${repo.fullName}`, target: '_blank', rel: 'noopener noreferrer' }, 'GitHub')];
  const homepage = d.homepage[repo.index];
  if (homepage && /^https?:\/\//i.test(homepage)) {
    out.push(h('a', { class: 'chip', href: homepage, target: '_blank', rel: 'noopener noreferrer' }, '项目主页'));
  }
  for (const [platform, url] of d.funding[repo.index] ?? []) {
    if (/^https?:\/\//i.test(url)) out.push(h('a', { class: 'chip', href: url, target: '_blank', rel: 'noopener noreferrer' }, `赞助：${platform}`));
  }
  out.push(h('span', { class: 'note' }, `元数据获取于 ${dateTime((d.fetched_at[repo.index] ?? 0) * 1000)}`));
  return out;
}

async function fillReadme(el: HTMLElement, repo: Repo, signal: AbortSignal): Promise<void> {
  const path = (await loadDetails()).readme_path[repo.index];
  if (!path) {
    mount(el, h('p', { class: 'muted' }, '该项目没有 Markdown 格式的 README。'));
    return;
  }
  mount(el, h('p', { class: 'loading' }, '正在从 GitHub 加载 README（需要联网）…'));
  try {
    const content = await loadReadme(repo.fullName, path, signal);
    mount(el, h('article', { class: 'markdown' }, content), h('p', { class: 'note' }, `来源：github.com/${repo.fullName} 的 ${path}。链接与图片指向 GitHub。`));
  } catch (error) {
    if (signal.aborted) return;
    mount(el, h('p', { class: 'error' }, error instanceof Error ? error.message : 'README 加载失败'));
  }
}
