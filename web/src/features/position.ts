import type { Repo } from '../data/model';

/** 某项目在总榜某项指标上的位置。排名 1 表示数值最大。 */
export interface Position {
  value: number;
  min: number;
  median: number;
  max: number;
  rank: number;
  total: number;
  /** 0–1。按对数刻度从最小值到最大值；跨度不足时退化为线性。 */
  fraction: number;
}

export function metricPosition(all: readonly number[], value: number): Position | null {
  if (all.length === 0) return null;
  const sorted = [...all].sort((a, b) => a - b);
  const min = sorted[0] as number;
  const max = sorted[sorted.length - 1] as number;
  const mid = sorted.length >> 1;
  const median = sorted.length % 2 ? (sorted[mid] as number) : ((sorted[mid - 1] as number) + (sorted[mid] as number)) / 2;
  // 比它大的项目数 + 1。并列时取并列中最靠前的名次。
  const rank = 1 + sorted.length - upperBound(sorted, value);
  const scale = (x: number) => (min > 0 ? Math.log(x) : Math.log1p(x - min));
  const span = scale(max) - scale(min);
  const fraction = span > 0 ? (scale(value) - scale(min)) / span : 0.5;
  return { value, min, median, max, rank, total: sorted.length, fraction: Math.min(1, Math.max(0, fraction)) };
}

/** 第一个大于 value 的位置。 */
function upperBound(sorted: readonly number[], value: number): number {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    if ((sorted[m] as number) <= value) lo = m + 1;
    else hi = m;
  }
  return lo;
}

export const POSITION_METRICS: { label: string; value: (r: Repo) => number | null }[] = [
  { label: 'Star', value: (r) => r.stars },
  { label: 'Fork', value: (r) => r.forks },
  { label: 'Watch', value: (r) => r.watchers },
  { label: '贡献者', value: (r) => r.contributors },
  { label: '提交数', value: (r) => r.commits },
  { label: '未关 Issue', value: (r) => r.openIssues },
  { label: '未合 PR', value: (r) => r.openPrs },
  { label: '发布数', value: (r) => r.releases },
];

/** 各指标的有效值，只算一次。 */
export function metricValues(repos: readonly Repo[]): Map<string, number[]> {
  return new Map(
    POSITION_METRICS.map((m) => [
      m.label,
      repos.map((r) => m.value(r)).filter((v): v is number => v != null),
    ]),
  );
}
