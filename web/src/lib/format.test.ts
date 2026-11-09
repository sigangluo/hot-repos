import { describe, expect, it } from 'vitest';
import { ageText, ago, compact, date, int, percent } from './format';

describe('format', () => {
  it('缺失值显示为破折号', () => {
    expect([int(null), compact(undefined), date(null), ageText(null)]).toEqual(['—', '—', '—', '—']);
  });

  it('数量缩写', () => {
    expect([999, 1000, 1234, 12_345, 561_150, 1_234_567, 12_345_678].map(compact)).toEqual([
      '999', '1k', '1.2k', '12k', '561k', '1.2M', '12M',
    ]);
  });

  it('千分位', () => {
    expect(int(1234567)).toBe('1,234,567');
  });

  it('日期按 UTC 显示', () => {
    expect(date(Date.UTC(2026, 0, 1, 23, 59))).toBe('2026-01-01');
  });

  it('时间跨度的单位随长度变化', () => {
    expect([10, 59, 60, 400, 730, 4000].map(ageText)).toEqual(['10 天', '59 天', '2 个月', '13 个月', '2.0 年', '11.0 年']);
  });

  it('距今多久', () => {
    const now = Date.UTC(2026, 0, 10);
    expect(ago(now - 10 * 60_000, now)).toBe('不到 1 小时前');
    expect(ago(now - 5 * 3_600_000, now)).toBe('5 小时前');
    expect(ago(now - 72 * 3_600_000, now)).toBe('3 天前');
  });

  it('百分比', () => {
    expect(percent(0.256, 1)).toBe('25.6%');
    expect(percent(Number.NaN)).toBe('—');
  });
});
