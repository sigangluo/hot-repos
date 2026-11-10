import { describe, expect, it } from 'vitest';
import { buildRepos, licenseClass, type Repo } from '../data/model';
import { buildTaxonomy } from '../data/taxonomy';
import { NOW, classification, columns, makeRepos } from '../test-utils';
import {
  GROUPS,
  activeCount,
  ageBucket,
  applyFilters,
  categoryCounts,
  emptyFilters,
  facetCounts,
  paginate,
  pushBucket,
  sortRepos,
  type Filters,
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

describe('分类筛选', () => {
  // 节点：0 开发、1 工具、2 命令行、3 编辑器、4 人工智能、5 智能体
  // a/cli：开发›工具›命令行（关联 人工智能›智能体）；b/editor：开发›编辑器；c/none：未分类
  const data = makeRepos(
    [{ full_name: 'a/cli' }, { full_name: 'b/editor' }, { full_name: 'c/none' }],
    classification([[2, [5], [0]], [3, [], [0, 1]], [null, [], []]]),
  );
  const group = (id: string) => GROUPS.find((g) => g.id === id)!;
  const names = (filters: Filters) => applyFilters(data, filters).map((r) => r.fullName);
  const inCategories = (scope: 'primary' | 'all', ...nodes: number[]): Filters => ({
    ...emptyFilters(),
    categoryScope: scope,
    categories: new Set(nodes),
  });

  it('项目带出主分类路径、关联路径、形态，以及路径上的全部节点', () => {
    expect(data[0]).toMatchObject({
      category: ['开发', '工具', '命令行'],
      relatedPaths: [['人工智能', '智能体']],
      forms: ['应用'],
      categoryNodes: [0, 1, 2],
      relatedNodes: [4, 5],
    });
    expect(data[2]).toMatchObject({ category: [], relatedPaths: [], categoryNodes: [], relatedNodes: [], forms: [] });
  });

  it('选中某一级即包含其下全部子分类', () => {
    expect(names(inCategories('primary', 0))).toEqual(['a/cli', 'b/editor']);
    expect(names(inCategories('primary', 1))).toEqual(['a/cli']);
    expect(names(inCategories('primary', 2))).toEqual(['a/cli']);
  });

  it('多个选中的分类取并集，未分类的项目选中任何分类后都不出现', () => {
    expect(names(inCategories('primary', 2, 3))).toEqual(['a/cli', 'b/editor']);
    expect(names(inCategories('primary', 0, 1, 2, 3, 4, 5))).not.toContain('c/none');
  });

  it('默认只看主分类，切到“含关联分类”后关联分类也算', () => {
    expect(names(inCategories('primary', 4))).toEqual([]);
    expect(names(inCategories('all', 4))).toEqual(['a/cli']);
    expect(names(inCategories('all', 5))).toEqual(['a/cli']);
  });

  it('分类树各节点的数量：父节点包含子节点，每个项目只计一次', () => {
    const counts = categoryCounts(data, emptyFilters());
    expect([0, 1, 2, 3, 4].map((n) => counts.get(n) ?? 0)).toEqual([2, 1, 1, 1, 0]);
    // 含关联分类时，a/cli 同时落在开发与人工智能下，各计一次
    const all = categoryCounts(data, { ...emptyFilters(), categoryScope: 'all' });
    expect([0, 4, 5].map((n) => all.get(n))).toEqual([2, 1, 1]);
  });

  it('分类数量不受分类自身的选择影响，但受其他条件影响', () => {
    const counts = categoryCounts(data, { ...inCategories('primary', 2), text: 'editor' });
    expect(counts.get(0)).toBe(1);
    expect(counts.get(2)).toBeUndefined();
  });

  it('选中的分类计入已选条件数', () => {
    expect(activeCount(inCategories('primary', 1, 3))).toBe(2);
  });

  it('可按项目形态筛选，多值取任一', () => {
    const filters = { ...emptyFilters(), selected: { form: new Set(['库']) } };
    expect(names(filters)).toEqual(['b/editor']);
  });

  it('搜索能命中分类名称', () => {
    expect(names({ ...emptyFilters(), text: '编辑器' })).toEqual(['b/editor']);
  });

  it('没有分类数据时，项目形态分组不可用', () => {
    expect(group('form').available?.(makeRepos([{}]))).toBe(false);
    expect(group('form').available?.(data)).toBe(true);
  });
});

describe('定义', () => {
  it('每个筛选分组都有定义', () => {
    for (const g of GROUPS) expect(g.definition.trim().length, g.id).toBeGreaterThan(10);
  });

  it('选项定义与选项一一对应：有固定选项顺序的分组，定义的键就是这些选项', () => {
    for (const g of GROUPS) {
      if (!g.order || typeof g.optionDefinitions !== 'object') continue;
      expect(Object.keys(g.optionDefinitions).sort(), g.id).toEqual([...g.order].sort());
    }
  });

  it('项目形态的选项定义来自分类目录', () => {
    const form = GROUPS.find((g) => g.id === 'form')!;
    const defs = (form.optionDefinitions as (t: ReturnType<typeof buildTaxonomy> | null) => Record<string, string>)(
      buildTaxonomy(classification([])),
    );
    expect(defs).toEqual({ 应用: '直接使用的应用', 库: '供程序引用的代码库' });
    expect((form.optionDefinitions as (t: null) => Record<string, string>)(null)).toEqual({});
  });
});
