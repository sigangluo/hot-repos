// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { buildTaxonomy } from '../data/taxonomy';
import type { Meta } from '../data/types';
import { Store } from '../state/store';
import { NOW, classification, makeRepos, schemeInfo } from '../test-utils';
import type { Ctx } from './context';
import { dayWithAge, renderSchemePicker, schemeAge, schemeFacts } from './scheme-picker';

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

describe('体系的新旧', () => {
  const day = (iso: string) => Date.parse(iso);

  it('日期后面跟距今多久', () => {
    expect(dayWithAge('2026-01-10', day('2026-01-10'))).toBe('2026-01-10（今天）');
    expect(dayWithAge('2026-01-03', day('2026-01-10'))).toBe('2026-01-03（7 天前）');
    expect(dayWithAge('2017-06-08', day('2026-11-10'))).toBe('2017-06-08（9.4 年前）');
  });

  it('一行文字给出创建、最近更新；超过 1 年没更新时明说', () => {
    const fresh = schemeInfo({ created: '2025-01-01', updated: '2026-01-03' });
    expect(schemeAge(fresh, day('2026-01-10'))).toBe('创建 2025-01-01（12 个月前） · 最近更新 2026-01-03（7 天前）');
    const old = schemeInfo({ created: '2017-06-08', updated: '2020-01-24' });
    expect(schemeAge(old, day('2026-01-10'))).toContain('已超过 1 年没有更新');
  });
});

describe('schemeFacts', () => {
  const NOW_MS = NOW;

  it('本站自己的体系：标注方式、时间和覆盖范围，没有来源', () => {
    const facts = schemeFacts(SITE, 5000, NOW_MS);
    expect(facts.map(([label]) => label)).toEqual(['标注方式', '创建', '最近更新', '覆盖范围']);
    expect(facts[3]?.[1]).toContain('361 / 5,000');
    expect(String(facts[2]?.[1])).toContain('2026-01-09');
  });

  it('外部体系：来源链接、许可、取得日期、署名和注意事项', () => {
    const facts = new Map(schemeFacts(BORGES, 5000, NOW_MS));
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

  it('下拉框下面一行显示创建与最近更新', () => {
    const root = renderSchemePicker(ctxOf(SITE))!;
    expect(root.querySelector('.scheme-age')?.textContent).toContain('创建 2026-01-01');
    expect(root.querySelector('.scheme-age')?.textContent).toContain('最近更新 2026-01-09');
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
