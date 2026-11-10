// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta } from '../data/types';
import { Store } from '../state/store';
import { NOW, classification, makeRepos } from '../test-utils';
import { renderFilters } from './filters';
import type { Ctx } from './context';

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 3, repos: 3, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, classified: 2,
};

// 开发›工具›命令行（a/cli，关联 人工智能›智能体）、开发›编辑器（b/editor）、未分类（c/none）
const FILE = classification([[2, [5], [0]], [3, [], [0, 1]], [null, [], []]], '仅供参考的说明');

function setup() {
  const repos = makeRepos([{ full_name: 'a/cli' }, { full_name: 'b/editor' }, { full_name: 'c/none' }], FILE);
  const store = new Store();
  const ctx: Ctx = { meta: META, repos, taxonomy: buildTaxonomy(FILE), now: NOW, store, weeks: null };
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

  it('初始只显示有项目的一级分类和数量，并显示目录附带的说明', () => {
    const { rows, root } = setup();
    expect(rows()).toEqual(['开发2']);
    expect(root.querySelector('.group .note')?.textContent).toBe('仅供参考的说明');
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

  it('分类树上方有分类的定义', () => {
    const { root } = setup();
    expect(root.querySelector('.group .def')?.textContent).toContain('按项目服务的领域归类');
  });
});
