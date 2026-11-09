import { COLUMNS, type ColumnKey } from '../features/columns';

export type Theme = 'auto' | 'light' | 'dark';

export const PAGE_SIZES = [10, 20, 50] as const;

export interface Prefs {
  theme: Theme;
  pageSize: number;
  /** 用户选择的列；没有保存过为 null，使用默认列。 */
  columns: ColumnKey[] | null;
}

const PREFIX = 'hot-repos:';

function read(key: string): unknown {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw == null ? null : JSON.parse(raw);
  } catch {
    return null;
  }
}

/** 读取偏好；保存的值不合法（比如旧版本的列已不存在）时忽略。 */
export function loadPrefs(): Prefs {
  const theme = read('theme');
  const pageSize = read('pageSize');
  const columns = read('columns');
  const known = new Set<string>(COLUMNS.map((c) => c.key));
  const valid = Array.isArray(columns) ? columns.filter((c): c is ColumnKey => known.has(c)) : [];
  return {
    theme: theme === 'light' || theme === 'dark' ? theme : 'auto',
    pageSize: PAGE_SIZES.includes(pageSize as 10) ? (pageSize as number) : 10,
    columns: valid.length > 0 ? valid : null,
  };
}

export function savePref(key: keyof Prefs, value: unknown): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // 隐私模式等场景下无法保存，忽略即可。
  }
}
