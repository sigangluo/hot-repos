import { describe, expect, it } from 'vitest';
import type { TrendingFile } from '../data/types';
import { makeRepos } from '../test-utils';
import { buildTrending } from './trending';

function file(rows: Partial<Record<string, unknown>>[]): TrendingFile {
  const pick = <T>(key: string, fallback: T) => rows.map((r) => (key in r ? (r[key] as T) : fallback));
  return {
    snapshot_date: '2026-01-10',
    captured_at: 0,
    languages: [['all', '全部语言'], ['go', 'Go']],
    rows: {
      since: pick('since', 'daily'),
      language: pick('language', 'all'),
      rank: pick('rank', 1),
      full_name: pick('full_name', 'a/b'),
      description: pick('description', null),
      repo_language: pick('repo_language', null),
      stars: pick('stars', 10),
      forks: pick('forks', 1),
      period_stars: pick('period_stars', 3),
      built_by: pick('built_by', [] as string[]),
    },
  };
}

describe('Trending 榜单', () => {
  it('按（时间段，语言）分组并按页面名次排序', () => {
    const model = buildTrending(
      file([
        { rank: 2, full_name: 'x/two' },
        { rank: 1, full_name: 'x/one' },
        { since: 'weekly', full_name: 'x/week' },
        { language: 'go', full_name: 'x/go' },
      ]),
      [],
    );
    expect(model.list('daily', 'all').map((i) => i.fullName)).toEqual(['x/one', 'x/two']);
    expect(model.list('weekly', 'all').map((i) => i.fullName)).toEqual(['x/week']);
    expect(model.list('daily', 'go').map((i) => i.fullName)).toEqual(['x/go']);
  });

  it('没有上榜项目的榜单为空数组', () => {
    expect(buildTrending(file([{}]), []).list('monthly', 'go')).toEqual([]);
  });

  it('标出总榜中的项目，忽略大小写，并沿用总榜里的写法', () => {
    const repos = makeRepos([{ rank: 7, full_name: 'Owner/Repo' }]);
    const items = buildTrending(file([{ full_name: 'owner/repo' }, { rank: 2, full_name: 'other/x' }]), repos).list('daily', 'all');
    expect(items[0]).toMatchObject({ boardRank: 7, boardName: 'Owner/Repo' });
    expect(items[1]).toMatchObject({ boardRank: null, boardName: null });
  });

  it('保留缺失的简介与语言，以及头像用户名', () => {
    const [item] = buildTrending(file([{ built_by: ['alice', 'bob'], stars: 190258 }]), []).list('daily', 'all');
    expect(item).toMatchObject({ description: null, language: null, builtBy: ['alice', 'bob'], stars: 190258 });
  });
});
