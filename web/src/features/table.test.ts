// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';
import type { Meta } from '../data/types';
import { Store } from '../state/store';
import { buildTaxonomy } from '../data/taxonomy';
import { classification, makeRepos, NOW } from '../test-utils';
import type { Ctx } from './context';
import { renderResults } from './table';

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 25, repos: 25, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: [NOW / 1000, NOW / 1000], star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, classified: 0,
};

function setup() {
  const repos = makeRepos(
    Array.from({ length: 25 }, (_, i) => ({
      rank: i + 1,
      full_name: `owner${i + 1}/repo${i + 1}`,
      stars: 1000 - i * 10,
      primary_language: i % 5 === 0 ? 'Go' : 'Python',
    })),
  );
  const store = new Store();
  const ctx: Ctx = { meta: META, repos, taxonomy: null, now: NOW, store, weeks: null };
  const root = renderResults(ctx);
  document.body.replaceChildren(root);
  const names = () => [...root.querySelectorAll('tbody tr .name')].map((a) => a.textContent);
  const summary = () => root.querySelector('.summary')?.textContent ?? '';
  return { store, root, names, summary };
}

beforeEach(() => localStorage.clear());

describe('结果表格', () => {
  it('默认按名次显示第一页', () => {
    const { names, summary } = setup();
    expect(names()).toHaveLength(10);
    expect(names()[0]).toBe('owner1/repo1');
    expect(summary()).toBe('共 25 个项目');
  });

  it('没有分类数据时不显示分类列，有分类数据时显示', () => {
    const headers = (root: HTMLElement) => [...root.querySelectorAll('thead th')].map((th) => th.textContent?.replace(/[↑↓ ]/g, ''));
    expect(headers(setup().root)).not.toContain('分类');

    const file = classification([[2, [], []]]);
    const repos = makeRepos([{ full_name: 'a/b' }], file);
    const root = renderResults({ meta: META, repos, taxonomy: buildTaxonomy(file), now: NOW, store: new Store(), weeks: null });
    expect(headers(root)).toContain('分类');
    expect(root.querySelector('tbody td.clip')?.textContent).toBe('开发 › 工具 › 命令行');
  });

  it('翻页与每页条数', () => {
    const { store, names, root } = setup();
    store.set({ page: 3 });
    expect(names()).toEqual(['owner21/repo21', 'owner22/repo22', 'owner23/repo23', 'owner24/repo24', 'owner25/repo25']);
    expect(root.querySelector('.pager')?.textContent).toContain('3 / 3');
    store.set({ pageSize: 50 });
    expect(names()).toHaveLength(25);
    expect(store.state.page).toBe(1);
  });

  it('点击表头排序，再点一次反向', () => {
    const { store, root, names } = setup();
    const header = () => [...root.querySelectorAll('th button')].find((b) => b.textContent?.startsWith('Star')) as HTMLButtonElement;
    header().click();
    expect(store.state.sortKey).toBe('stars');
    expect(store.state.sortDirection).toBe('desc');
    expect(names()[0]).toBe('owner1/repo1');
    header().click();
    expect(store.state.sortDirection).toBe('asc');
    expect(names()[0]).toBe('owner25/repo25');
    expect(root.querySelector('th[aria-sort="ascending"]')).not.toBeNull();
  });

  it('筛选后更新数量并显示可移除的条件', () => {
    const { store, summary, root, names } = setup();
    store.set({ filters: { ...store.state.filters, selected: { language: new Set(['Go']) } } });
    expect(summary()).toBe('共 5 个项目（全部 25 个）');
    expect(names()).toHaveLength(5);
    const chip = root.querySelector<HTMLButtonElement>('.chips .chip');
    expect(chip?.textContent).toBe('主要语言：Go');
    chip?.click();
    expect(summary()).toBe('共 25 个项目');
  });

  it('没有结果时给出提示', () => {
    const { store, root } = setup();
    store.set({ filters: { ...store.state.filters, text: 'no-such-project' } });
    expect(root.querySelector('.empty-state')?.textContent).toContain('没有符合条件');
  });

  it('列设置：取消勾选后该列消失，名次和项目名不可取消', () => {
    const { store, root } = setup();
    expect(root.querySelector('th')?.textContent).toContain('名次');
    const labels = [...root.querySelectorAll('.menu .option')].map((l) => l.textContent);
    expect(labels).not.toContain('名次');
    expect(labels).not.toContain('项目');
    store.set({ columns: store.state.columns.filter((c) => c !== 'forks') });
    expect([...root.querySelectorAll('th')].map((t) => t.textContent)).not.toContain('Fork');
  });

  it('项目名是文本而不是 HTML', () => {
    const repos = makeRepos([{ full_name: 'o/<img src=x onerror=alert(1)>', description: '<b>bold</b>' }]);
    const store = new Store();
    const root = renderResults({ meta: META, repos, taxonomy: null, now: NOW, store, weeks: null });
    expect(root.querySelector('tbody img, tbody b')).toBeNull();
    expect(root.querySelector('tbody .name')?.textContent).toContain('<img');
  });
});
