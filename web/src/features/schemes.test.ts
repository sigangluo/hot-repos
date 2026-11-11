// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta, SchemeFile } from '../data/types';
import { Store } from '../state/store';
import { NOW, classification, makeRepos, schemeInfo } from '../test-utils';
import type { Ctx } from './context';
import { initialScheme, switchScheme } from './schemes';

const MAIN = classification([[2, [5]], [3, []], [null, []]]);
// 另一个没有主分类的体系：a/cli 属于“甲”和“乙”，其余都没收录
const OTHER: SchemeFile = {
  nodes: [['a', -1, '甲', null, null], ['b', -1, '乙', null, null]],
  category: [null, null, null], related: [[0, 1], [], []],
};

const files = new Map<string, SchemeFile>([['main', MAIN], ['other', OTHER]]);
vi.mock('../data/schemes', () => ({
  getScheme: (id: string) => {
    const file = files.get(id);
    return file ? Promise.resolve({ file, taxonomy: buildTaxonomy(file) }) : Promise.reject(new Error('加载失败'));
  },
}));

const INFOS = [schemeInfo(), schemeInfo({ id: 'other', name: '另一个', primary: false, classified: 1 }), schemeInfo({ id: 'gone' })];
const META = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 3, repos: 3, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, schemes: INFOS,
} satisfies Meta;

function setup(): Ctx {
  const repos = makeRepos([{ full_name: 'a/cli' }, { full_name: 'b/editor' }, { full_name: 'c/none' }]);
  return { meta: META, repos, scheme: null, taxonomy: null, now: NOW, store: new Store(), weeks: null };
}

beforeEach(() => localStorage.clear());

describe('initialScheme', () => {
  it('用上次选过且仍存在的体系，否则用第一个', () => {
    expect(initialScheme(INFOS, 'other')).toBe('other');
    expect(initialScheme(INFOS, 'removed')).toBe('main');
    expect(initialScheme(INFOS, null)).toBe('main');
  });

  it('没有体系时为 null', () => {
    expect(initialScheme([], 'main')).toBeNull();
  });
});

describe('switchScheme', () => {
  it('把体系应用到全部项目，并记下选择', async () => {
    const ctx = setup();
    await switchScheme(ctx, 'main');
    expect(ctx.scheme?.id).toBe('main');
    expect(ctx.store.state.scheme).toBe('main');
    expect(ctx.repos[0]?.category).toEqual(['开发', '工具', '命令行']);
    expect(ctx.repos[2]?.category).toEqual([]);
    expect(localStorage.getItem('hot-repos:scheme')).toBe('"main"');
  });

  it('切到另一个体系：旧分类被换掉，分类节点条件被清掉，其余条件保留', async () => {
    const ctx = setup();
    await switchScheme(ctx, 'main');
    const { store } = ctx;
    store.set({ filters: { ...store.state.filters, text: 'cli', categories: new Set([1]), selected: { language: new Set(['Python']) } } });
    await switchScheme(ctx, 'other');
    expect(ctx.repos[0]?.category).toEqual([]);
    expect(ctx.repos[0]?.relatedPaths).toEqual([['甲'], ['乙']]);
    expect(ctx.repos[1]?.relatedPaths).toEqual([]);
    const { filters } = store.state;
    expect([...filters.categories]).toEqual([]);
    expect([...(filters.selected.language ?? [])]).toEqual(['Python']);
    expect(filters.text).toBe('cli');
  });

  it('搜索文本跟着体系变：能搜到当前体系的分类名，搜不到旧体系的', async () => {
    const ctx = setup();
    await switchScheme(ctx, 'main');
    expect(ctx.repos[0]?.haystack).toContain('命令行');
    await switchScheme(ctx, 'other');
    expect(ctx.repos[0]?.haystack).not.toContain('命令行');
    expect(ctx.repos[0]?.haystack).toContain('乙');
  });

  it('没有主分类的体系把范围设为“含关联分类”，有主分类的设回“仅主分类”', async () => {
    const ctx = setup();
    await switchScheme(ctx, 'other');
    expect(ctx.store.state.filters.categoryScope).toBe('all');
    await switchScheme(ctx, 'main');
    expect(ctx.store.state.filters.categoryScope).toBe('primary');
  });

  it('体系文件加载失败时页面不带分类，其余照常', async () => {
    const ctx = setup();
    await switchScheme(ctx, 'main');
    await switchScheme(ctx, 'gone');
    expect(ctx.scheme).toBeNull();
    expect(ctx.taxonomy).toBeNull();
    expect(ctx.store.state.scheme).toBeNull();
    expect(ctx.repos[0]?.category).toEqual([]);
  });

  it('订阅者能收到体系变化', async () => {
    const ctx = setup();
    const seen: string[] = [];
    ctx.store.subscribe((state, changed) => changed.has('scheme') && seen.push(String(state.scheme)));
    await switchScheme(ctx, 'other');
    await switchScheme(ctx, 'main');
    expect(seen).toEqual(['other', 'main']);
  });
});
