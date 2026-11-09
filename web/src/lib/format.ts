const DASH = '—';

export function int(n: number | null | undefined): string {
  return n == null ? DASH : Math.round(n).toLocaleString('en-US');
}

/** 561150 → 561k，1234567 → 1.2M */
export function compact(n: number | null | undefined): string {
  if (n == null) return DASH;
  const a = Math.abs(n);
  const trim = (x: number, digits: number) => x.toFixed(digits).replace(/\.0$/, '');
  if (a >= 1e6) return trim(n / 1e6, a >= 1e7 ? 0 : 1) + 'M';
  if (a >= 1e3) return trim(n / 1e3, a >= 1e4 ? 0 : 1) + 'k';
  return String(Math.round(n));
}

/** 日期按 UTC 显示，与数据口径一致。 */
export function date(ms: number | null | undefined): string {
  return ms == null ? DASH : new Date(ms).toISOString().slice(0, 10);
}

/** 本地时区的 YYYY-MM-DD HH:mm。 */
export function dateTime(ms: number | null | undefined): string {
  if (ms == null) return DASH;
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function ageText(days: number | null | undefined): string {
  if (days == null) return DASH;
  if (days < 60) return `${Math.round(days)} 天`;
  if (days < 730) return `${Math.round(days / 30.4)} 个月`;
  return `${(days / 365.25).toFixed(1)} 年`;
}

/** 距某时刻过去了多久，如“3 小时前”。 */
export function ago(ms: number, now = Date.now()): string {
  const hours = (now - ms) / 3_600_000;
  if (hours < 1) return '不到 1 小时前';
  if (hours < 48) return `${Math.round(hours)} 小时前`;
  return `${Math.round(hours / 24)} 天前`;
}

export function percent(x: number, digits = 0): string {
  return Number.isFinite(x) ? `${(x * 100).toFixed(digits)}%` : DASH;
}
