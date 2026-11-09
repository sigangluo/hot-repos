// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';
import type { Meta, TrendingFile } from '../data/types';
import { Store } from '../state/store';
import { makeRepos, NOW } from '../test-utils';
import type { Ctx } from './context';
import { renderTrending, renderTrendingPage } from './trending';

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 5, repos: 5, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: '2026-01-10',
};

const FILE: TrendingFile = {
  snapshot_date: '2026-01-10',
  captured_at: NOW / 1000,
  languages: [['all', '全部语言'], ['go', 'Go']],
  rows: {
    since: ['daily', 'daily', 'weekly', 'daily'],
    language: ['all', 'all', 'all', 'go'],
    rank: [1, 2, 1, 1],
    full_name: ['Owner/Known', 'new/<img src=x onerror=alert(1)>', 'new/weekly', 'new/gopher'],
    description: ['已在总榜', '<b>粗体</b>', null, null],
    repo_language: ['Python', null, 'Go', 'Go'],
    stars: [190258, 5, 7, 9],
    forks: [22397, 1, 1, 1],
    period_stars: [1052, 30, 500, 40],
    built_by: [['alice', 'bob', 'c', 'd', 'e', 'f'], [], [], []],
  },
};

function setup(file: TrendingFile = FILE) {
  const repos = makeRepos([{ rank: 28, full_name: 'Owner/Known' }]);
  const ctx: Ctx = { meta: META, repos, now: NOW, store: new Store(), weeks: null };
  const root = renderTrending(ctx, file);
  document.body.replaceChildren(root);
  const names = () => [...root.querySelectorAll('.trend-item .name')].map((a) => a.textContent);
  return { ctx, root, names };
}

beforeEach(() => localStorage.clear());

describe('近期热点', () => {
  it('默认显示今日、全部语言的榜单', () => {
    const { names, root } = setup();
    expect(names()).toEqual(['Owner / Known', 'new / <img src=x onerror=alert(1)>']);
    expect(root.querySelector('.summary')?.textContent).toBe('共 2 个项目');
    expect(root.querySelector('[data-since="daily"]')?.getAttribute('aria-pressed')).toBe('true');
  });

  it('总榜中的项目链接到站内详情并标出名次，其余跳到 GitHub', () => {
    const { root } = setup();
    const [known, other] = root.querySelectorAll<HTMLAnchorElement>('.trend-item .name');
    expect(known?.getAttribute('href')).toBe('#/Owner/Known');
    expect(known?.target).toBe('');
    expect(root.querySelector('.trend-item .chip')?.textContent).toBe('总榜第 28 名');
    expect(other?.target).toBe('_blank');
    expect(other?.rel).toBe('noopener noreferrer');
    expect(root.querySelectorAll('.chip')).toHaveLength(1);
  });

  it('显示该时间段新增 Star，切换时间段与语言后更新榜单', () => {
    const { root, names } = setup();
    expect(root.querySelector('.trend-gain')?.textContent).toBe('+1,052今日新增 Star');
    root.querySelector<HTMLButtonElement>('[data-since="weekly"]')?.click();
    expect(names()).toEqual(['new / weekly']);
    expect(root.querySelector('.trend-gain')?.textContent).toContain('本周新增 Star');
    const select = root.querySelector('select')!;
    select.value = 'go';
    select.dispatchEvent(new Event('change'));
    expect(root.querySelector('.empty-state')?.textContent).toContain('没有上榜项目');
    root.querySelector<HTMLButtonElement>('[data-since="daily"]')?.click();
    expect(names()).toEqual(['new / gopher']);
  });

  it('简介和名称按文本显示，头像最多 5 个', () => {
    const { root } = setup();
    expect(root.querySelector('.trend-main img:not(.avatar), .trend-main b')).toBeNull();
    expect(root.querySelectorAll('.trend-item:first-child .avatar')).toHaveLength(5);
    expect(root.querySelector('.avatar')?.getAttribute('src')).toBe('https://github.com/alice.png?size=40');
  });

  it('头像加载失败时移除，不留破图', () => {
    const { root } = setup();
    root.querySelector('.avatar')?.dispatchEvent(new Event('error'));
    expect(root.querySelectorAll('.trend-item:first-child .avatar')).toHaveLength(4);
  });
});

describe('近期热点页面', () => {
  const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

  it('第一次切换到该视图时才加载，之后不重复加载', async () => {
    const store = new Store();
    const ctx: Ctx = { meta: META, repos: [], now: NOW, store, weeks: null };
    let loads = 0;
    const host = renderTrendingPage(ctx, () => (loads++, Promise.resolve(FILE)));
    expect(host.hidden).toBe(true);
    expect(loads).toBe(0);
    store.set({ view: 'trending' });
    await flush();
    expect(host.hidden).toBe(false);
    expect(host.querySelector('.trend-item')).not.toBeNull();
    store.set({ view: 'board' });
    store.set({ view: 'trending' });
    expect(host.hidden).toBe(false);
    expect(loads).toBe(1);
  });

  it('加载失败时给出提示，可以重试', async () => {
    const store = new Store();
    store.set({ view: 'trending' });
    const ctx: Ctx = { meta: META, repos: [], now: NOW, store, weeks: null };
    let fail = true;
    const host = renderTrendingPage(ctx, () => (fail ? Promise.reject(new Error('HTTP 500')) : Promise.resolve(FILE)));
    await flush();
    expect(host.querySelector('.error')?.textContent).toContain('HTTP 500');
    fail = false;
    host.querySelector<HTMLButtonElement>('button')?.click();
    await flush();
    expect(host.querySelector('.trend-item')).not.toBeNull();
  });
});
