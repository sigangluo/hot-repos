// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { SPARK_WEEKS, sparkline } from './sparkline';

const bars = (svg: SVGSVGElement) => [...svg.querySelectorAll('rect')];

describe('sparkline', () => {
  it('没有数据时是空图并带说明', () => {
    for (const input of [null, []]) {
      const svg = sparkline(input);
      expect(bars(svg)).toHaveLength(0);
      expect(svg.getAttribute('aria-label')).toContain('无');
    }
  });

  it('只画最近 SPARK_WEEKS 周', () => {
    expect(bars(sparkline(Array.from({ length: 100 }, (_, i) => i)))).toHaveLength(SPARK_WEEKS);
  });

  it('每个项目独立缩放：最大值撑满高度，零值只有细线', () => {
    const heights = bars(sparkline([0, 5, 10])).map((r) => Number(r.getAttribute('height')));
    expect(heights[2]).toBeCloseTo(22);
    expect(heights[1]).toBeCloseTo(11);
    expect(heights[0]).toBe(1);
  });

  it('数据不足一页时靠右排列，左侧留白', () => {
    const xs = bars(sparkline([1, 1])).map((r) => Number(r.getAttribute('x')));
    expect(xs[0]).toBeGreaterThan(80);
  });
});
