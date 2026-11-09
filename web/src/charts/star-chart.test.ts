import { describe, expect, it } from 'vitest';
import { cumulative, weekLabels } from './star-chart';

describe('star-chart helpers', () => {
  it('周标签从起始日起每 7 天一个，按 UTC 计算', () => {
    expect(weekLabels('2026-01-04', 3)).toEqual(['2026-01-04', '2026-01-11', '2026-01-18']);
    expect(weekLabels('2026-03-01', 2)).toEqual(['2026-03-01', '2026-03-08']); // 跨夏令时不错位
  });

  it('累计只是已收录周的累加', () => {
    expect(cumulative([3, 0, 5])).toEqual([3, 3, 8]);
    expect(cumulative([])).toEqual([]);
  });
});
