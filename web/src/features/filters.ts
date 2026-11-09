import { h, mount } from '../lib/dom';
import { int } from '../lib/format';
import { GROUPS, activeCount, emptyFilters, facetCounts, type Filters, type Group, type Range } from '../state/query';
import type { Ctx } from './context';

/** 记住各分组的展开状态与“显示全部”，重绘面板时不丢失。 */
const open = new Set<string>(['language', 'license']);
const expanded = new Set<string>();

export function renderFilters(ctx: Ctx): HTMLElement {
  const { store, repos } = ctx;
  const root = h('aside', { class: 'filters', 'aria-label': '筛选' });

  const setSelected = (group: Group, value: string, on: boolean) => {
    const { filters } = store.state;
    const next = new Set(filters.selected[group.id] ?? []);
    if (on) next.add(value);
    else next.delete(value);
    store.set({ filters: { ...filters, selected: { ...filters.selected, [group.id]: next } } });
  };

  const rangeField = (label: string, key: 'stars' | 'contributors') => {
    const { filters } = store.state;
    const parse = (input: HTMLInputElement) => (input.value.trim() === '' ? null : Math.max(0, Number(input.value)));
    const make = (placeholder: string, value: number | null, side: keyof Range) => {
      const input = h('input', {
        class: 'input',
        type: 'number',
        min: 0,
        inputmode: 'numeric',
        placeholder,
        value: value ?? '',
        'aria-label': `${label}${placeholder}`,
      });
      // 输入完成（失焦或回车）后才生效，避免每敲一个数字就重绘整个面板。
      input.addEventListener('change', () => {
        const range = { ...store.state.filters[key], [side]: parse(input) };
        store.set({ filters: { ...store.state.filters, [key]: range } });
      });
      return input;
    };
    return h(
      'div',
      null,
      h('div', { class: 'field-label' }, label),
      h('div', { class: 'range' }, make('最小', filters[key].min, 'min'), '–', make('最大', filters[key].max, 'max')),
    );
  };

  const renderGroup = (group: Group, filters: Filters) => {
    const selected = filters.selected[group.id] ?? new Set<string>();
    const all = facetCounts(repos, filters, group);
    const showAll = expanded.has(group.id);
    const visible = group.limit && !showAll ? all.filter(([v], i) => i < group.limit! || selected.has(v)) : all;
    const options = visible.map(([value, count]) =>
      h(
        'label',
        { class: count === 0 ? 'option empty' : 'option' },
        h('input', {
          type: 'checkbox',
          checked: selected.has(value),
          onchange: (e: Event) => setSelected(group, value, (e.target as HTMLInputElement).checked),
        }),
        h('span', null, value),
        h('span', { class: 'count' }, int(count)),
      ),
    );
    // checked 是 DOM 属性而非 attribute，需要显式设置。
    options.forEach((label, i) => {
      const box = label.querySelector('input');
      if (box) box.checked = selected.has(visible[i]?.[0] ?? '');
    });
    const details = h(
      'details',
      { class: 'group', open: open.has(group.id) || selected.size > 0 },
      h('summary', null, h('span', null, group.label), selected.size ? h('span', { class: 'badge' }, `已选 ${selected.size}`) : null),
      group.allowAll
        ? h(
            'span',
            { class: 'seg', role: 'group', 'aria-label': `${group.label}匹配方式` },
            h('button', { type: 'button', 'aria-pressed': String(!filters.matchAll[group.id]), onclick: () => setMatch(group, false) }, '满足任一'),
            h('button', { type: 'button', 'aria-pressed': String(!!filters.matchAll[group.id]), onclick: () => setMatch(group, true) }, '满足全部'),
          )
        : null,
      h('div', { class: 'options' }, options),
      group.limit && all.length > group.limit
        ? h(
            'button',
            {
              type: 'button',
              class: 'link-btn',
              onclick: () => {
                if (showAll) expanded.delete(group.id);
                else expanded.add(group.id);
                draw();
              },
            },
            showAll ? '收起' : `显示全部 ${all.length} 项`,
          )
        : null,
    );
    details.addEventListener('toggle', () => {
      if (details.open) open.add(group.id);
      else open.delete(group.id);
    });
    return details;
  };

  const setMatch = (group: Group, matchAll: boolean) => {
    const { filters } = store.state;
    store.set({ filters: { ...filters, matchAll: { ...filters.matchAll, [group.id]: matchAll } } });
  };

  const draw = () => {
    const { filters } = store.state;
    mount(
      root,
      h(
        'div',
        { class: 'filters-head' },
        h('h2', null, '筛选'),
        h('button', { type: 'button', class: 'btn', disabled: activeCount(filters) === 0, onclick: () => store.set({ filters: emptyFilters() }) }, '清除全部'),
      ),
      rangeField('Star 数', 'stars'),
      rangeField('贡献者数', 'contributors'),
      ...GROUPS.map((g) => renderGroup(g, filters)),
    );
  };

  draw();
  store.subscribe((_, changed) => changed.has('filters') && draw());
  return root;
}
