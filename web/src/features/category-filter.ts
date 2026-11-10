import { categoryDefinition } from '../data/glossary';
import type { Taxonomy } from '../data/taxonomy';
import { h } from '../lib/dom';
import { int } from '../lib/format';
import { categoryCounts, type CategoryScope, type Filters } from '../state/query';
import type { Ctx } from './context';

/** 记住展开的分支，重绘面板时不丢失；跟随页面的 Store，互不干扰。 */
const expandedByStore = new WeakMap<object, Set<number>>();
/** 展开了定义说明的节点，同样跟随 Store。 */
const definitionsByStore = new WeakMap<object, Set<number>>();


const SCOPES: readonly [CategoryScope, string][] = [
  ['primary', '仅主分类'],
  ['all', '含关联分类'],
];

/**
 * 分类筛选：一棵可展开的树（最多三级），每一级都可勾选，勾选即包含其下全部子分类。
 * 数量是“满足其他全部条件”时该分类下的项目数；没有项目的分支不显示（已选的除外）。
 * 没有层级的体系（如各种合集）按项目数从多到少排列。
 */
export function renderCategoryGroup(ctx: Ctx, taxonomy: Taxonomy, filters: Filters, open: Set<string>): HTMLElement {
  const { store } = ctx;
  const primary = ctx.scheme?.primary ?? true;
  const expanded = expandedByStore.get(store) ?? expandedByStore.set(store, new Set()).get(store)!;
  const shownDefs = definitionsByStore.get(store) ?? definitionsByStore.set(store, new Set()).get(store)!;
  const counts = categoryCounts(ctx.repos, filters);
  const { categories } = filters;

  const hasSelectedBelow = (node: number): boolean =>
    taxonomy.children(node).some((c) => categories.has(c) || hasSelectedBelow(c));

  const choose = (node: number, on: boolean) => {
    const next = new Set(store.state.filters.categories);
    if (on) {
      // 选中一个节点后，它的上级和下级不必再单独保留：上级已被收窄，下级已被它包含。
      for (const n of taxonomy.pathNodes(node)) next.delete(n);
      const drop = (n: number) => taxonomy.children(n).forEach((c) => (next.delete(c), drop(c)));
      drop(node);
      next.add(node);
    } else next.delete(node);
    store.set({ filters: { ...store.state.filters, categories: next } });
  };

  const byCount = (a: number, b: number) =>
    (counts.get(b) ?? 0) - (counts.get(a) ?? 0) || taxonomy.label(a).localeCompare(taxonomy.label(b));
  const item = (node: number, depth = 0): HTMLElement | null => {
    const count = counts.get(node) ?? 0;
    const selected = categories.has(node);
    const below = hasSelectedBelow(node);
    if (count === 0 && !selected && !below) return null;
    // 没有主分类的体系（合集、清单），一级分类下的第二级也按项目数排（如清单分组下的各个清单）；再往下保持原文顺序。
    const kids = !primary && depth === 0 ? [...taxonomy.children(node)].sort(byCount) : taxonomy.children(node);
    const children = kids.map((c) => item(c, depth + 1)).filter((c): c is HTMLElement => c !== null);
    const isOpen = children.length > 0 && (expanded.has(node) || below);
    const name = taxonomy.label(node);
    const box = h('input', {
      type: 'checkbox',
      onchange: (e: Event) => choose(node, (e.target as HTMLInputElement).checked),
    });
    // checked / indeterminate 是 DOM 属性而非 attribute，需要显式设置。
    box.checked = selected;
    box.indeterminate = !selected && below;
    const toggle = children.length
      ? h('button', {
          type: 'button',
          class: 'tree-toggle',
          'aria-expanded': String(isOpen),
          'aria-label': `${isOpen ? '收起' : '展开'}${name}`,
          onclick: () => {
            if (isOpen) expanded.delete(node);
            else expanded.add(node);
            store.set({ filters: { ...store.state.filters } }); // 只为触发重绘
          },
        }, isOpen ? '▾' : '▸')
      : taxonomy.flat ? null : h('span', { class: 'tree-toggle' }); // 没有层级时不留展开按钮的空位
    const { includes, excludes } = taxonomy.definition(node);
    const defOpen = shownDefs.has(node);
    const info =
      includes || excludes
        ? h('button', {
            type: 'button',
            class: 'info',
            'aria-expanded': String(defOpen),
            'aria-label': `${name}的说明`,
            onclick: () => {
              if (defOpen) shownDefs.delete(node);
              else shownDefs.add(node);
              store.set({ filters: { ...store.state.filters } }); // 只为触发重绘
            },
          }, 'ⓘ')
        : null;
    return h('li', null,
      h('div', { class: 'tree-row' }, toggle,
        h('label', { class: 'option' }, box, h('span', null, name), h('span', { class: 'count' }, int(count))), info),
      defOpen
        ? h('div', { class: 'def-block' },
            includes ? h('p', null, h('b', null, '收：'), includes) : null,
            excludes ? h('p', null, h('b', null, '不收：'), excludes) : null)
        : null,
      isOpen ? h('ul', { class: 'tree' }, children) : null);
  };

  const setScope = (categoryScope: CategoryScope) =>
    store.set({ filters: { ...store.state.filters, categoryScope } });

  const roots = taxonomy.flat || !primary
    ? [...taxonomy.roots].sort(byCount)
    : taxonomy.roots;
  const details = h('details', { class: 'group', open: open.has('category') || categories.size > 0 },
    h('summary', null, h('span', null, '分类'), categories.size ? h('span', { class: 'badge' }, `已选 ${categories.size}`) : null),
    h('p', { class: 'def' }, categoryDefinition(primary)),
    primary
      ? h('span', { class: 'seg', role: 'group', 'aria-label': '分类范围' },
          SCOPES.map(([scope, label]) =>
            h('button', { type: 'button', 'aria-pressed': String(filters.categoryScope === scope), onclick: () => setScope(scope) }, label)))
      : null,
    h('ul', { class: 'tree root' }, roots.map((r) => item(r))));
  details.addEventListener('toggle', () => {
    if (details.open) open.add('category');
    else open.delete('category');
  });
  return details;
}
