// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { DATA_TIMES, FACTS } from '../data/glossary';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta } from '../data/types';
import { GROUPS } from '../state/query';
import { Store } from '../state/store';
import { NOW, classification, makeRepos, schemeInfo } from '../test-utils';
import { COLUMNS } from './columns';
import type { Ctx } from './context';
import { renderGlossary } from './glossary';

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 1, repos: 1, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, schemes: [],
};

function render(withClassification: boolean, trending = false) {
  const file = classification([[2, []]]);
  const repos = makeRepos([{}], withClassification ? file : null);
  const info = schemeInfo({ name: '甲体系', source: { name: '某来源', url: 'https://example.com', license: 'CC-BY-4.0' }, as_of: '2026-01-09' });
  const ctx: Ctx = {
    meta: { ...META, trending_date: trending ? '2026-01-10' : null, schemes: withClassification ? [info, schemeInfo({ id: 'b', name: '乙体系' })] : [] },
    repos,
    scheme: withClassification ? info : null,
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
    for (const g of GROUPS) expect(text).toContain(g.label);
  });

  it('许可证各类别的定义也在其中', () => {
    const text = render(false).textContent ?? '';
    for (const name of ['宽松', 'Copyleft', '其他', '未声明']) expect(text).toContain(`${name}：`);
  });

  it('没有分类数据时不出现分类和一级分类', () => {
    const el = render(false);
    const headings = [...el.querySelectorAll('h3')].map((h) => h.textContent);
    expect(headings.some((t) => t?.startsWith('一级分类'))).toBe(false);
    expect(headings).not.toContain('分类体系');
  });

  it('有分类数据时列出一级分类的收录说明', () => {
    const el = render(true);
    expect([...el.querySelectorAll('h3')].map((h) => h.textContent)).toContain('一级分类（甲体系）');
    expect(el.textContent).toContain('写代码的工具与方法');
  });

  it('列出每个分类体系的标注方式、覆盖范围、来源与许可', () => {
    const el = render(true);
    const text = el.textContent ?? '';
    for (const word of ['甲体系', '乙体系', '语言模型判断', '某来源', 'CC-BY-4.0', '取得于 2026-01-09', '2 / 1 个项目']) expect(text).toContain(word);
  });

  it('近期热点的名词只在有 Trending 数据时出现', () => {
    expect(render(false, false).textContent).not.toContain('今日 / 本周 / 本月新增 Star');
    expect(render(false, true).textContent).toContain('今日 / 本周 / 本月新增 Star');
  });
});
