// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta } from '../data/types';
import { Store } from '../state/store';
import { NOW, classification, makeRepos, schemeInfo } from '../test-utils';
import type { Ctx } from './context';
import { renderSchemePicker, schemeFacts } from './scheme-picker';

const switchScheme = vi.fn(() => Promise.resolve());
vi.mock('./schemes', () => ({ switchScheme: (...args: unknown[]) => switchScheme(...(args as [])) }));

const SOURCE = { name: 'Borges 等', url: 'https://example.com/data', license: 'CC-BY-4.0', attribution: '某某著，2017' };
const BORGES = schemeInfo({ id: 'borges', name: 'Borges 人工分类', method: 'manual', source: SOURCE, as_of: '2026-01-09', note: '2017 年的数据', primary: true, classified: 987 });
const SITE = schemeInfo({ classified: 361 });

const META: Meta = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 5000, repos: 5000, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, schemes: [SITE, BORGES],
};

function ctxOf(current: typeof SITE | null, schemes = META.schemes): Ctx {
  const file = classification([[2, [], []]]);
  return { meta: { ...META, schemes }, repos: makeRepos([{}], file), scheme: current, taxonomy: current ? buildTaxonomy(file) : null, now: NOW, store: new Store(), weeks: null };
}

beforeEach(() => switchScheme.mockClear());

describe('schemeFacts', () => {
  it('本站自己的体系：标注方式和覆盖范围，没有来源', () => {
    const labels = schemeFacts(SITE, 5000).map(([label]) => label);
    expect(labels).toEqual(['标注方式', '覆盖范围']);
    expect(schemeFacts(SITE, 5000)[1]?.[1]).toContain('361 / 5,000');
  });

  it('外部体系：来源链接、许可、取得日期、署名和注意事项', () => {
    const facts = new Map(schemeFacts(BORGES, 5000));
    const source = facts.get('来源') as HTMLElement;
    expect(source.querySelector('a')?.getAttribute('href')).toBe('https://example.com/data');
    expect(source.textContent).toContain('CC-BY-4.0');
    expect(source.textContent).toContain('取得于 2026-01-09');
    expect(facts.get('署名')).toBe('某某著，2017');
    expect(facts.get('注意')).toBe('2017 年的数据');
    expect(String(facts.get('标注方式'))).toContain('研究者人工标注');
  });
});

describe('分类体系选择', () => {
  it('没有分类体系时不显示', () => {
    expect(renderSchemePicker(ctxOf(null, []))).toBeNull();
  });

  it('下拉框列出每个体系和覆盖数，当前体系被选中，并显示简介', () => {
    const root = renderSchemePicker(ctxOf(SITE))!;
    const options = [...root.querySelectorAll('option')].map((o) => o.textContent);
    expect(options).toEqual(['测试体系（361 个项目）', 'Borges 人工分类（987 个项目）']);
    expect(root.querySelector('select')?.value).toBe('site');
    expect(root.querySelector('.def')?.textContent).toBe('用于测试的体系');
  });

  it('选另一个体系时切换', () => {
    const ctx = ctxOf(SITE);
    const root = renderSchemePicker(ctx)!;
    const select = root.querySelector('select')!;
    select.value = 'borges';
    select.dispatchEvent(new Event('change'));
    expect(switchScheme).toHaveBeenCalledWith(ctx, 'borges');
  });

  it('“关于这个体系”里有来源与许可', () => {
    const root = renderSchemePicker(ctxOf(BORGES))!;
    expect(root.querySelector('details.defs summary')?.textContent).toBe('关于这个体系');
    expect(root.querySelector('details.defs')?.textContent).toContain('CC-BY-4.0');
  });

  it('当前体系加载失败时给出提示，仍可重新选择', () => {
    const root = renderSchemePicker(ctxOf(null))!;
    expect(root.querySelector('.error')?.textContent).toContain('加载失败');
    expect(root.querySelector('select')?.value).toBe('');
  });
});
