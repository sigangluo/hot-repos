const SVG = 'http://www.w3.org/2000/svg';
const WIDTH = 96;
const HEIGHT = 22;
export const SPARK_WEEKS = 30;

/** 周 Star 迷你柱状图：取最近 SPARK_WEEKS 周，每个项目独立缩放；缺失的周留白。 */
export function sparkline(stars: readonly number[] | null): SVGSVGElement {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('class', 'spark');
  svg.setAttribute('width', String(WIDTH));
  svg.setAttribute('height', String(HEIGHT));
  svg.setAttribute('viewBox', `0 0 ${WIDTH} ${HEIGHT}`);
  svg.setAttribute('role', 'img');
  if (!stars || stars.length === 0) {
    svg.setAttribute('aria-label', '无周 Star 数据');
    return svg;
  }
  const recent = stars.slice(-SPARK_WEEKS);
  const max = Math.max(...recent, 1);
  const slot = WIDTH / SPARK_WEEKS;
  // 数据不足 SPARK_WEEKS 周时靠右排列，左侧留白。
  const offset = (SPARK_WEEKS - recent.length) * slot;
  svg.setAttribute('aria-label', `最近 ${recent.length} 周，最高每周 ${max} 个 Star`);
  recent.forEach((value, i) => {
    const height = value === 0 ? 1 : Math.max(2, (value / max) * HEIGHT);
    const bar = document.createElementNS(SVG, 'rect');
    bar.setAttribute('x', (offset + i * slot + 0.5).toFixed(2));
    bar.setAttribute('y', (HEIGHT - height).toFixed(2));
    bar.setAttribute('width', (slot - 1).toFixed(2));
    bar.setAttribute('height', height.toFixed(2));
    bar.setAttribute('fill', 'currentColor');
    bar.setAttribute('opacity', value === 0 ? '0.25' : '1');
    svg.append(bar);
  });
  return svg;
}
