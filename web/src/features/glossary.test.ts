// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { DATA_TIMES, FACTS } from '../data/glossary';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta } from '../data/types';
import { GROUPS } from '../state/query';
import { Store } from '../state/store';
import { NOW, classification, makeRepos } from '../test-utils';
import { COLUMNS } from './columns';
import type { Ctx } from './context';
import { renderGlossary } from './glossary';

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 1, repos: 1, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, classified: 0,
};

function render(withClassification: boolean, trending = false) {
  const file = classification([[2, [], [0]]]);
  const repos = makeRepos([{}], withClassification ? file : null);
  const ctx: Ctx = {
    meta: { ...META, trending_date: trending ? '2026-01-10' : null },
    repos,
    taxonomy: withClassification ? buildTaxonomy(file) : null,
    now: NOW,
    store: new Store(),
    weeks: null,
  };
  return renderGlossary(ctx);
}

describe('名词与口径说明', () => {
  it('默认折叠，标题是“名词与口径说明”', () => {
    const el = render(false);
    expect(el.tagName).toBe('DETAILS');
    expect((el as HTMLDetailsElement).open).toBe(false);
    expect(el.querySelector('summary')?.textContent).toBe('名词与口径说明');
  });

  it('覆盖数据时点、详情指标、全部表格列和筛选分组', () => {
    const text = render(false).textContent ?? '';
    for (const [label] of DATA_TIMES) expect(text).toContain(label);
    for (const label of Object.keys(FACTS)) expect(text).toContain(label);
    for (const c of COLUMNS.filter((c) => !('needsClassification' in c))) expect(text).toContain(c.label);
    for (const g of GROUPS.filter((g) => g.id !== 'form')) expect(text).toContain(g.label);
  });

  it('许可证各类别的定义也在其中', () => {
    const text = render(false).textContent ?? '';
    for (const name of ['宽松', 'Copyleft', '其他', '未声明']) expect(text).toContain(`${name}：`);
  });

  it('没有分类数据时不出现分类、项目形态和一级分类', () => {
    const el = render(false);
    const headings = [...el.querySelectorAll('h3')].map((h) => h.textContent);
    expect(headings).not.toContain('一级分类');
    expect(el.textContent).not.toContain('项目形态');
  });

  it('有分类数据时列出一级分类的收录说明和形态定义', () => {
    const el = render(true);
    expect([...el.querySelectorAll('h3')].map((h) => h.textContent)).toContain('一级分类');
    expect(el.textContent).toContain('写代码的工具与方法');
    expect(el.textContent).toContain('直接使用的应用');
  });

  it('近期热点的名词只在有 Trending 数据时出现', () => {
    expect(render(false, false).textContent).not.toContain('今日 / 本周 / 本月新增 Star');
    expect(render(false, true).textContent).toContain('今日 / 本周 / 本月新增 Star');
  });
});
