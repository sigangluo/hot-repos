// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta, SchemeFile } from '../data/types';
import { Store } from '../state/store';
import { NOW, classification, makeRepos, schemeInfo } from '../test-utils';
import { renderFilters } from './filters';
import type { Ctx } from './context';

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 3, repos: 3, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, schemes: [],
};

// 开发›工具›命令行（a/cli，关联 人工智能›智能体）、开发›编辑器（b/editor）、未分类（c/none）
const FILE = classification([[2, [5]], [3, []], [null, []]]);

function setup(file = FILE, info = schemeInfo()) {
  const repos = makeRepos([{ full_name: 'a/cli' }, { full_name: 'b/editor' }, { full_name: 'c/none' }], file);
  const store = new Store();
  const ctx: Ctx = { meta: { ...META, schemes: [info] }, repos, scheme: info, taxonomy: buildTaxonomy(file), now: NOW, store, weeks: null };
  const root = renderFilters(ctx);
  document.body.replaceChildren(root);
  const rows = () =>
    [...root.querySelectorAll('.tree-row')].map((r) => r.querySelector('.option')?.textContent ?? '');
  const row = (name: string) => [...root.querySelectorAll('.tree-row')].find((r) => r.querySelector('.option span')?.textContent === name) as HTMLElement;
  const box = (name: string) => row(name).querySelector('input') as HTMLInputElement;
  const expand = (name: string) => row(name).querySelector<HTMLButtonElement>('.tree-toggle')?.click();
  return { store, root, rows, row, box, expand };
}

describe('分类树', () => {
  beforeEach(() => {
    document.body.replaceChildren();
  });

  it('初始只显示有项目的一级分类和数量', () => {
    const { rows } = setup();
    expect(rows()).toEqual(['开发2']);
  });

  it('展开后显示子分类，再展开显示第三级；没有项目的分支不出现', () => {
    const { rows, expand } = setup();
    expand('开发');
    expect(rows()).toEqual(['开发2', '工具1', '编辑器1']);
    expand('工具');
    expect(rows()).toEqual(['开发2', '工具1', '命令行1', '编辑器1']);
  });

  it('勾选父级筛选其下全部项目，子级随之收窄时替换父级', () => {
    const { store, box, expand } = setup();
    box('开发').click();
    expect([...store.state.filters.categories]).toEqual([0]);
    expand('开发');
    box('工具').click();
    expect([...store.state.filters.categories]).toEqual([1]);
  });

  it('选中子分类时，未选的父级显示为半选并自动展开', () => {
    const { box, expand } = setup();
    expand('开发');
    box('编辑器').click();
    expect(box('开发').indeterminate).toBe(true);
    expect(box('开发').checked).toBe(false);
    expect(box('编辑器').checked).toBe(true);
  });

  it('切到“含关联分类”后，关联分类所在的一级也出现', () => {
    const { store, root, rows } = setup();
    expect(rows()).toEqual(['开发2']);
    const scope = [...root.querySelectorAll<HTMLButtonElement>('.seg button')].find((b) => b.textContent === '含关联分类');
    scope?.click();
    expect(store.state.filters.categoryScope).toBe('all');
    expect(rows()).toEqual(['开发2', '人工智能1']);
  });

  it('有说明的分类带 ⓘ，点开显示收录与排除；没有说明的不带', () => {
    const { root, row } = setup();
    const info = (name: string) => row(name).querySelector<HTMLButtonElement>('.info');
    expect(info('开发')?.getAttribute('aria-expanded')).toBe('false');
    expect(root.querySelector('.def-block')).toBeNull();
    info('开发')?.click();
    expect(info('开发')?.getAttribute('aria-expanded')).toBe('true');
    expect(root.querySelector('.def-block')?.textContent).toContain('写代码的工具与方法');
  });

  it('分类树上方有分类的定义，有主分类的体系说明主分类与关联分类', () => {
    const { root } = setup();
    expect(root.querySelector('.group .def')?.textContent).toContain('一个项目有一个主分类'.replace('一个项目有', '每个项目有'));
  });

  it('没有主分类的体系：没有“仅主分类”切换，一个项目可以属于多个分类', () => {
    // 没有主分类时全部分类都在 related 里；节点 3 编辑器在 a/cli 与 b/editor 都有
    const flat = { ...FILE, category: [null, null, null], related: [[2, 3], [3], []] };
    const { root, rows, store } = setup(flat, schemeInfo({ primary: false }));
    store.set({ filters: { ...store.state.filters, categoryScope: 'all' } }); // switchScheme 会这样设置
    expect(root.querySelector('[aria-label="分类范围"]')).toBeNull();
    expect(root.querySelector('.group .def')?.textContent).toContain('可以同时属于多个分类');
    expect(rows()).toEqual(['开发2']);
  });

  it('没有层级的体系按项目数从多到少排列', () => {
    const flatFile = {
      nodes: [['a', -1, '甲', null, null], ['b', -1, '乙', null, null], ['c', -1, '丙', null, null]] as SchemeFile['nodes'],
      category: [null, null, null], related: [[0], [1], [1]],
    };
    const { store, rows } = setup(flatFile, schemeInfo({ primary: false }));
    store.set({ filters: { ...store.state.filters, categoryScope: 'all' } });
    expect(rows()).toEqual(['乙2', '甲1']);
  });
});

describe('分类树：没有主分类的体系，第二级也按项目数排', () => {
  // 两个分组（甲、乙），甲下有清单 a（1 个项目）、b（2 个项目）；乙下有清单 c（1 个项目）。项目 0 属于 a、b，项目 1 属于 b，项目 2 属于 c。
  const file: SchemeFile = {
    nodes: [
      ['g1', -1, '甲', null, null], ['g1.a', 0, '清单A', null, null], ['g1.b', 0, '清单B', null, null],
      ['g1.b.s', 2, '章节', null, null], ['g2', -1, '乙', null, null], ['g2.c', 4, '清单C', null, null],
    ],
    category: [null, null, null], related: [[1, 2], [3], [5]],
  };

  function drawn() {
    const info = schemeInfo({ primary: false });
    const repos = makeRepos([{ full_name: 'a/x' }, { full_name: 'b/y' }, { full_name: 'c/z' }], file);
    const store = new Store();
    store.set({ filters: { ...store.state.filters, categoryScope: 'all' } });
    const ctx: Ctx = { meta: { ...META, schemes: [info] }, repos, scheme: info, taxonomy: buildTaxonomy(file), now: NOW, store, weeks: null };
    const root = renderFilters(ctx);
    document.body.replaceChildren(root);
    return { root, store };
  }

  it('一级分组和其下的清单都按项目数从多到少，更深的章节保持原文顺序', () => {
    const { root } = drawn();
    const rows = () => [...root.querySelectorAll('.tree-row .option')].map((r) => r.textContent);
    expect(rows()).toEqual(['甲2', '乙1']);
    root.querySelector<HTMLButtonElement>('.tree-toggle')?.click();
    expect(rows()).toEqual(['甲2', '清单B2', '清单A1', '乙1']); // 清单B 项目更多，排在清单A 前面
  });
});

describe('分类名是总榜里的项目时可以打开详情', () => {
  // 一级分类 a/cli 的名字恰好是总榜里的项目（如 Awesome 清单），一级分类“开发”不是
  const file: SchemeFile = {
    nodes: [['dev', -1, '开发', null, null], ['dev.a-cli', 0, 'A/CLI', null, null]],
    category: [null, null], related: [[1], []],
  };

  it('是项目的分类带“打开详情”链接，指向项目的详情地址；不是的没有', () => {
    const info = schemeInfo({ primary: false });
    const repos = makeRepos([{ full_name: 'a/cli' }, { full_name: 'b/editor' }], file);
    const store = new Store();
    store.set({ filters: { ...store.state.filters, categoryScope: 'all' } });
    const ctx: Ctx = { meta: { ...META, schemes: [info] }, repos, scheme: info, taxonomy: buildTaxonomy(file), now: NOW, store, weeks: null };
    const root = renderFilters(ctx);
    document.body.replaceChildren(root);
    root.querySelector<HTMLButtonElement>('.tree-toggle')?.click(); // 展开“开发”
    const links = [...root.querySelectorAll<HTMLAnchorElement>('.tree a.repo-link')];
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['#/a/cli']); // 忽略大小写对上 a/cli，用总榜里的写法
    expect(links[0]?.getAttribute('aria-label')).toBe('打开 A/CLI 的详情');
    expect(root.querySelector('.tree-row .option span')?.textContent).toBe('开发');
  });
});
