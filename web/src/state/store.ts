import { emptyFilters, type Filters, type SortDirection } from './query';
import { loadPrefs, savePref, type Theme } from './prefs';
import { DEFAULT_COLUMNS, type ColumnKey } from '../features/columns';
import type { View } from './route';

export interface AppState {
  filters: Filters;
  sortKey: ColumnKey;
  sortDirection: SortDirection;
  page: number;
  pageSize: number;
  columns: ColumnKey[];
  theme: Theme;
  view: View;
  /** 详情抽屉打开的项目；null 表示关闭。 */
  openRepo: string | null;
  /** 当前使用的分类体系编号；null 表示没有可用的体系。 */
  scheme: string | null;
}

type Listener = (state: AppState, changed: ReadonlySet<keyof AppState>) => void;

/** 极简状态容器：修改后通知订阅者，并带上变化的字段，订阅者只重绘自己关心的部分。 */
export class Store {
  private listeners: Listener[] = [];
  state: AppState;

  constructor() {
    const prefs = loadPrefs();
    this.state = {
      filters: emptyFilters(),
      sortKey: 'rank',
      sortDirection: 'asc',
      page: 1,
      pageSize: prefs.pageSize,
      columns: prefs.columns ?? [...DEFAULT_COLUMNS],
      theme: prefs.theme,
      view: 'board',
      openRepo: null,
      scheme: null,
    };
  }

  /** 订阅状态变化，返回取消订阅的函数。 */
  subscribe(listener: Listener): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  set(patch: Partial<AppState>): void {
    const changed = new Set<keyof AppState>();
    for (const key of Object.keys(patch) as (keyof AppState)[]) {
      if (patch[key] !== this.state[key]) changed.add(key);
    }
    if (changed.size === 0) return;
    this.state = { ...this.state, ...patch };
    // 筛选、排序、每页条数变化后回到第一页。
    if (
      !('page' in patch) &&
      (changed.has('filters') || changed.has('sortKey') || changed.has('sortDirection') || changed.has('pageSize'))
    ) {
      this.state = { ...this.state, page: 1 };
      changed.add('page');
    }
    if (changed.has('theme')) savePref('theme', this.state.theme);
    if (changed.has('columns')) savePref('columns', this.state.columns);
    if (changed.has('pageSize')) savePref('pageSize', this.state.pageSize);
    if (changed.has('scheme') && this.state.scheme) savePref('scheme', this.state.scheme);
    // 复制一份再遍历：订阅者可能在回调里新增或取消订阅。
    for (const listener of [...this.listeners]) listener(this.state, changed);
  }
}
