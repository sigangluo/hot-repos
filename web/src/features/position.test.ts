import { describe, expect, it } from 'vitest';
import { metricPosition } from './position';

describe('metricPosition', () => {
  const all = [1, 10, 100, 1000, 10000];

  it('给出最小值、中位数、最大值和名次', () => {
    const p = metricPosition(all, 100);
    expect(p).toMatchObject({ min: 1, median: 100, max: 10000, rank: 3, total: 5 });
  });

  it('对数刻度：10 的幂等间距', () => {
    expect(metricPosition(all, 1)?.fraction).toBeCloseTo(0);
    expect(metricPosition(all, 100)?.fraction).toBeCloseTo(0.5);
    expect(metricPosition(all, 10000)?.fraction).toBeCloseTo(1);
  });

  it('并列时取最靠前的名次', () => {
    expect(metricPosition([5, 5, 5, 1], 5)?.rank).toBe(1);
    expect(metricPosition([5, 5, 5, 1], 1)?.rank).toBe(4);
  });

  it('偶数个值的中位数取中间两数的平均', () => {
    expect(metricPosition([1, 2, 3, 4], 2)?.median).toBe(2.5);
  });

  it('含 0 的数据不会产生无穷大', () => {
    const p = metricPosition([0, 0, 5, 50], 5);
    expect(Number.isFinite(p?.fraction)).toBe(true);
    expect(p?.fraction).toBeGreaterThan(0);
  });

  it('所有值相同时居中；没有数据时为 null', () => {
    expect(metricPosition([7, 7, 7], 7)?.fraction).toBe(0.5);
    expect(metricPosition([], 1)).toBeNull();
  });
});
