// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { loadPrefs, savePref } from './prefs';
import { Store } from './store';

beforeEach(() => localStorage.clear());

describe('Store', () => {
  it('只在状态真的变化时通知，并说明变化了哪些字段', () => {
    const store = new Store();
    const listener = vi.fn();
    store.subscribe(listener);
    store.set({ pageSize: store.state.pageSize });
    expect(listener).not.toHaveBeenCalled();
    store.set({ sortDirection: 'desc' });
    expect(listener).toHaveBeenCalledTimes(1);
    expect([...(listener.mock.calls[0]?.[1] ?? [])]).toEqual(expect.arrayContaining(['sortDirection', 'page']));
  });

  it('筛选、排序、每页条数变化后回到第一页，翻页本身不会', () => {
    const store = new Store();
    store.set({ page: 4 });
    expect(store.state.page).toBe(4);
    store.set({ sortKey: 'stars' });
    expect(store.state.page).toBe(1);
    store.set({ page: 3 });
    store.set({ pageSize: 20 });
    expect(store.state.page).toBe(1);
    store.set({ page: 3, pageSize: 50 });
    expect(store.state.page).toBe(3);
  });

  it('取消订阅后不再通知', () => {
    const store = new Store();
    const listener = vi.fn();
    const off = store.subscribe(listener);
    off();
    store.set({ page: 2 });
    expect(listener).not.toHaveBeenCalled();
  });

  it('订阅者在回调中取消订阅不影响其他订阅者', () => {
    const store = new Store();
    const second = vi.fn();
    const off = store.subscribe(() => off());
    store.subscribe(second);
    store.set({ page: 2 });
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('主题、列和每页条数会保存，下次启动时恢复', () => {
    const first = new Store();
    first.set({ theme: 'dark', pageSize: 20, columns: ['rank', 'name', 'forks'] });
    const second = new Store();
    expect(second.state).toMatchObject({ theme: 'dark', pageSize: 20, columns: ['rank', 'name', 'forks'] });
  });
});

describe('loadPrefs', () => {
  it('没有保存过时使用默认值', () => {
    expect(loadPrefs()).toEqual({ theme: 'auto', pageSize: 10, columns: null, scheme: null });
  });

  it('忽略不合法的值和已经不存在的列', () => {
    savePref('theme', 'purple');
    savePref('pageSize', 7);
    savePref('columns', ['rank', 'removed-column', 'stars']);
    expect(loadPrefs()).toEqual({ theme: 'auto', pageSize: 10, columns: ['rank', 'stars'], scheme: null });
  });

  it('记住选择的分类体系，不是字符串的值忽略', () => {
    new Store().set({ scheme: 'borges' });
    expect(loadPrefs().scheme).toBe('borges');
    savePref('scheme', 5);
    expect(loadPrefs().scheme).toBeNull();
  });

  it('保存的内容损坏时不报错', () => {
    localStorage.setItem('hot-repos:columns', '{not json');
    expect(loadPrefs().columns).toBeNull();
  });
});
