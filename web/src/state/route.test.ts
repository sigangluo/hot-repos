import { describe, expect, it } from 'vitest';
import { parseHash, viewHash } from './route';

const names = new Set(['owner/repo']);

describe('地址解析', () => {
  it('空地址是总榜，趋势地址是近期热点', () => {
    expect(parseHash('', names)).toEqual({ view: 'board', openRepo: null });
    expect(parseHash('#', names)).toEqual({ view: 'board', openRepo: null });
    expect(parseHash('#/trending', names)).toEqual({ view: 'trending', openRepo: null });
  });

  it('项目地址只打开详情，不改变视图', () => {
    expect(parseHash('#/owner/repo', names)).toEqual({ view: null, openRepo: 'owner/repo' });
    expect(parseHash('#/owner%2Frepo', names).openRepo).toBe('owner/repo');
  });

  it('未收录的项目与损坏的编码都不打开详情', () => {
    expect(parseHash('#/nobody/nothing', names)).toEqual({ view: null, openRepo: null });
    expect(parseHash('#/%E0%A4%A', names)).toEqual({ view: null, openRepo: null });
  });

  it('视图对应的地址片段', () => {
    expect(viewHash('board')).toBe('');
    expect(viewHash('trending')).toBe('#/trending');
  });
});
