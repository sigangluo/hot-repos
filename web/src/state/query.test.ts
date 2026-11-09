import { describe, expect, it } from 'vitest';
import { buildRepos, licenseClass, type Repo } from '../data/model';
import { NOW, columns, makeRepos } from '../test-utils';
import {
  GROUPS,
  activeCount,
  ageBucket,
  applyFilters,
  emptyFilters,
  facetCounts,
  paginate,
  pushBucket,
  sortRepos,
} from './query';

const repos = makeRepos;

describe('buildRepos', () => {
  it('把列式数据还原为行，并换算时间', () => {
    const [r] = buildRepos(columns([{ full_name: 'a/b', description: 'Hi', topics: ['x'], pushed_at: null }]), NOW);
    expect(r).toMatchObject({ owner: 'a', name: 'b', isOrg: true, pushedAt: null, pushedDaysAgo: null });
    expect(r?.ageDays).toBeCloseTo(400);
    expect(r?.haystack).toContain('hi');
  });

  it('缺失的语言归入“未返回主语言”', () => {
    expect(repos([{ primary_language: null }])[0]?.language).toBe('未返回主语言');
  });
});

describe('分类', () => {
  it('许可证分为宽松、Copyleft、其他、未声明', () => {
    expect(['MIT', 'GPL-3.0', 'LGPL-2.1', 'NOASSERTION', null].map(licenseClass)).toEqual([
      '宽松', 'Copyleft', 'Copyleft', '其他', '未声明',
    ]);
  });

  it('推送与创建时长的分桶边界', () => {
    expect([0, 7, 8, 30, 90, 365, 366, null].map(pushBucket)).toEqual([
      '7 天内', '7 天内', '30 天内', '30 天内', '90 天内', '1 年内', '超过 1 年', '无推送记录',
    ]);
    expect([100, 400, 1500, 2500, 4000].map(ageBucket)).toEqual([
      '不足 1 年', '1–3 年', '3–5 年', '5–10 年', '10 年以上',
    ]);
  });
});

describe('筛选', () => {
  const data = repos([
    { rank: 1, full_name: 'a/web', description: 'A fast web server', stars: 900, topics: ['web', 'http'], primary_language: 'Go' },
    { rank: 2, full_name: 'b/ml', description: 'Machine learning', stars: 500, topics: ['ml', 'http'], primary_language: 'Python', contributors: null },
    { rank: 3, full_name: 'c/ui', description: null, stars: 100, topics: [], primary_language: 'Go', is_archived: true, license: null },
  ]);
  const names = (rs: Repo[]) => rs.map((r) => r.fullName);

  it('搜索按空格拆词，每个词都要命中名称、描述、话题或语言', () => {
    const f = { ...emptyFilters(), text: 'fast  GO' };
    expect(names(applyFilters(data, f))).toEqual(['a/web']);
  });

  it('同一分组内选中多个值是“满足任一”，话题可切换为“满足全部”', () => {
    const f = { ...emptyFilters(), selected: { topic: new Set(['web', 'ml']) } };
    expect(names(applyFilters(data, f))).toEqual(['a/web', 'b/ml']);
    expect(names(applyFilters(data, { ...f, matchAll: { topic: true } }))).toEqual([]);
    const both = { ...emptyFilters(), selected: { topic: new Set(['http', 'ml']) }, matchAll: { topic: true } };
    expect(names(applyFilters(data, both))).toEqual(['b/ml']);
  });

  it('不同分组之间是“并且”', () => {
    const f = { ...emptyFilters(), selected: { language: new Set(['Go']), archived: new Set(['未归档']) } };
    expect(names(applyFilters(data, f))).toEqual(['a/web']);
  });

  it('数值范围：缺失值在设置了范围时不通过', () => {
    const f = { ...emptyFilters(), contributors: { min: 1, max: null } };
    expect(names(applyFilters(data, f))).toEqual(['a/web', 'c/ui']);
    expect(names(applyFilters(data, { ...emptyFilters(), stars: { min: 200, max: 600 } }))).toEqual(['b/ml']);
  });

  it('选项数量只受其他条件影响，不受本组自身选择影响', () => {
    const language = GROUPS.find((g) => g.id === 'language')!;
    const f = { ...emptyFilters(), selected: { language: new Set(['Go']), archived: new Set(['未归档']) } };
    expect(facetCounts(data, f, language)).toEqual([['Go', 1], ['Python', 1]]);
  });

  it('已选中但数量为 0 的选项仍然保留', () => {
    const language = GROUPS.find((g) => g.id === 'language')!;
    const f = { ...emptyFilters(), text: 'machine', selected: { language: new Set(['Go']) } };
    expect(facetCounts(data, f, language)).toContainEqual(['Go', 0]);
  });

  it('有固定顺序的分组按该顺序排列', () => {
    const push = GROUPS.find((g) => g.id === 'pushed')!;
    expect(facetCounts(data, emptyFilters(), push).map(([k]) => k)).toEqual(['7 天内']);
  });

  it('统计已启用的条件数', () => {
    const f = { ...emptyFilters(), text: 'x', selected: { topic: new Set(['a', 'b']) }, stars: { min: 1, max: null } };
    expect(activeCount(f)).toBe(4);
  });
});

describe('排序与分页', () => {
  const data = repos([
    { rank: 1, full_name: 'a/a', stars: 30, contributors: 5 },
    { rank: 2, full_name: 'b/b', stars: 10, contributors: null },
    { rank: 3, full_name: 'c/c', stars: 20, contributors: 1 },
    { rank: 4, full_name: 'd/d', stars: 20, contributors: null },
  ]);
  const value = (r: Repo, k: 'stars' | 'contributors') => r[k];

  it('升降序，缺失值始终排最后', () => {
    expect(sortRepos(data, value, 'contributors', 'desc').map((r) => r.rank)).toEqual([1, 3, 2, 4]);
    expect(sortRepos(data, value, 'contributors', 'asc').map((r) => r.rank)).toEqual([3, 1, 2, 4]);
  });

  it('数值相同时按名次，结果稳定', () => {
    expect(sortRepos(data, value, 'stars', 'asc').map((r) => r.rank)).toEqual([2, 3, 4, 1]);
    expect(sortRepos(data, value, 'stars', 'desc').map((r) => r.rank)).toEqual([1, 3, 4, 2]);
  });

  it('不会改动原数组', () => {
    const before = data.map((r) => r.rank);
    sortRepos(data, value, 'stars', 'desc');
    expect(data.map((r) => r.rank)).toEqual(before);
  });

  it('分页并修正越界的页码', () => {
    const items = [1, 2, 3, 4, 5];
    expect(paginate(items, 2, 2)).toEqual({ items: [3, 4], page: 2, pages: 3, total: 5 });
    expect(paginate(items, 99, 2).page).toBe(3);
    expect(paginate(items, 0, 2).page).toBe(1);
    expect(paginate([], 5, 10)).toEqual({ items: [], page: 1, pages: 1, total: 0 });
  });
});
