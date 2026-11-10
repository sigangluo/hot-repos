// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';
import { buildTaxonomy } from '../data/taxonomy';
import type { DetailColumns, Meta, SchemeFile } from '../data/types';
import { Store } from '../state/store';
import { NOW, classification, makeRepos, schemeInfo } from '../test-utils';
import type { Ctx } from './context';
import { schemeCards } from './scheme-cards';

const SITE = classification([[2, [5], [0]], [null, [], []]]);
// 另一个没有主分类的体系：只收录了第一个项目
const OTHER: SchemeFile = {
  nodes: [['a', -1, '甲', '甲类收什么', null]],
  forms: [], category: [null, null], related: [[0], []], form: [[], []],
};
const files = new Map([['site', SITE], ['other', OTHER]]);
vi.mock('../data/schemes', () => ({
  getScheme: (id: string) => {
    const file = files.get(id);
    return file ? Promise.resolve({ file, taxonomy: buildTaxonomy(file) }) : Promise.reject(new Error('x'));
  },
}));

const SITE_INFO = schemeInfo();
const OTHER_INFO = schemeInfo({
  id: 'other', name: '外部体系', method: 'curated', primary: false,
  source: { name: '某来源', url: 'https://example.com', license: 'Apache-2.0' },
});
const META = {
  schema_version: 1, snapshot_date: '2026-01-10', board_size: 2, repos: 2, missing: 0,
  rank_captured_at: NOW / 1000, repos_fetched_at: null, star_weeks_fetched_at: null,
  star_weeks_per_page: 30, trending_date: null, schemes: [SITE_INFO, OTHER_INFO],
} satisfies Meta;

const DETAILS = { scheme_text: { site: { summary: ['一个命令行工具', null], review_reason: ['边界不清', null] } } } as unknown as DetailColumns;

function render(index: number, current = SITE_INFO) {
  const repos = makeRepos([{ full_name: 'a/cli' }, { full_name: 'b/none' }], SITE);
  const ctx: Ctx = { meta: META, repos, scheme: current, taxonomy: buildTaxonomy(SITE), now: NOW, store: new Store(), weeks: null };
  const host = schemeCards(ctx, repos[index]!, Promise.resolve(DETAILS));
  document.body.replaceChildren(host);
  return host;
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('详情里的分类卡片', () => {
  it('当前体系在前：主分类、关联分类、形态、简介、复核原因和各分类的说明', async () => {
    const host = render(0);
    await settle();
    const cards = [...host.querySelectorAll('section.card')];
    expect(cards.map((c) => c.querySelector('h3')?.textContent)).toEqual(['分类 · 测试体系 语言模型判断', '分类 · 外部体系 来源方人工策展']);
    const first = cards[0]!;
    expect(first.querySelector('.class-summary')?.textContent).toBe('一个命令行工具');
    expect(first.textContent).toContain('开发›工具›命令行');
    expect(first.textContent).toContain('人工智能›智能体');
    expect(first.textContent).toContain('应用');
    expect(first.textContent).toContain('标记为待复核：边界不清');
    expect(first.textContent).toContain('直接使用的应用'); // 形态“应用”的定义
  });

  it('其他体系也收录了这个项目时一并显示，没有主分类的体系列出“分类”，并注明来源与许可', async () => {
    const host = render(0);
    await settle();
    const other = host.querySelectorAll('section.card')[1]!;
    expect(other.querySelector('dt')?.textContent).toBe('分类');
    expect(other.textContent).toContain('甲：收甲类收什么'); // 分类的说明
    expect(other.querySelector('a')?.getAttribute('href')).toBe('https://example.com');
    expect(other.textContent).toContain('Apache-2.0');
  });

  it('当前体系没收录这个项目时说明一声，其他体系也没收录就不显示', async () => {
    const host = render(1);
    await settle();
    const cards = [...host.querySelectorAll('section.card')];
    expect(cards).toHaveLength(1);
    expect(cards[0]?.textContent).toContain('没有收录该项目');
  });

  it('没有任何分类体系时什么也不画', async () => {
    const repos = makeRepos([{}]);
    const ctx: Ctx = { meta: { ...META, schemes: [] }, repos, scheme: null, taxonomy: null, now: NOW, store: new Store(), weeks: null };
    const host = schemeCards(ctx, repos[0]!, Promise.resolve(DETAILS));
    await settle();
    expect(host.children).toHaveLength(0);
  });
});
