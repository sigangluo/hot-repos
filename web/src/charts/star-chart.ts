import type { ECharts } from 'echarts/core';
import { tokenColor } from '../lib/theme';

export type ChartMode = 'weekly' | 'cumulative';

const WEEK_MS = 7 * 86_400_000;

/** 第 i 周的起始日（UTC）。 */
export function weekLabels(start: string, count: number): string[] {
  const first = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: count }, (_, i) => new Date(first + i * WEEK_MS).toISOString().slice(0, 10));
}

export function cumulative(values: readonly number[]): number[] {
  let total = 0;
  return values.map((v) => (total += v));
}

// ECharts 体积大，只在第一次打开详情时才加载。
const loadEcharts = () => import('./echarts');

export interface StarChart {
  setMode(mode: ChartMode): void;
  /** 主题变化后按新的颜色重绘。 */
  restyle(): void;
  dispose(): void;
}

export async function createStarChart(el: HTMLElement, start: string, weekly: readonly number[], mode: ChartMode): Promise<StarChart> {
  const { init } = await loadEcharts();
  const chart: ECharts = init(el);
  const labels = weekLabels(start, weekly.length);
  const totals = cumulative(weekly);
  let current = mode;

  const draw = () => {
    const accent = tokenColor('--accent');
    const muted = tokenColor('--text-muted');
    const border = tokenColor('--border');
    const data = current === 'weekly' ? weekly : totals;
    chart.setOption(
      {
        animation: false,
        grid: { left: 48, right: 16, top: 16, bottom: 28 },
        tooltip: {
          trigger: 'axis',
          valueFormatter: (v: unknown) => Number(v).toLocaleString('en-US'),
        },
        xAxis: { type: 'category', data: labels, axisLabel: { color: muted }, axisLine: { lineStyle: { color: border } } },
        yAxis: { type: 'value', axisLabel: { color: muted }, splitLine: { lineStyle: { color: border } } },
        series: [
          current === 'weekly'
            ? { type: 'bar', name: '本周 Star', data, itemStyle: { color: accent } }
            : { type: 'line', name: '累计 Star', data, showSymbol: false, lineStyle: { color: accent }, areaStyle: { color: accent, opacity: 0.12 }, itemStyle: { color: accent } },
        ],
      },
      true,
    );
  };
  draw();

  const observer = new ResizeObserver(() => chart.resize());
  observer.observe(el);
  return {
    setMode(next) {
      current = next;
      draw();
    },
    restyle: draw,
    dispose() {
      observer.disconnect();
      chart.dispose();
    },
  };
}
