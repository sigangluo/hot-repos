import type { Repo } from '../data/model';
import { PATH_SEPARATOR } from '../data/taxonomy';
import { h, mount } from '../lib/dom';
import { int } from '../lib/format';
import { PAGE_SIZES } from '../state/prefs';
import { GROUPS, applyFilters, paginate, sortRepos, type Filters } from '../state/query';
import { COLUMNS, PINNED, column, sortValue, type ColumnKey } from './columns';
import { weeksOf, type Ctx } from './context';
import { sparkline } from './sparkline';

export function renderResults(ctx: Ctx): HTMLElement {
  const { store, repos } = ctx;

  // 筛选与排序的结果在条件不变时复用（翻页、切换列都不需要重新计算）。
  let memo: { filters: Filters; key: ColumnKey; direction: string; filtered: Repo[]; sorted: Repo[] } | null = null;
  const results = () => {
    const { filters, sortKey, sortDirection } = store.state;
    if (memo?.filters !== filters) {
      const filtered = applyFilters(repos, filters);
      memo = { filters, key: sortKey, direction: sortDirection, filtered, sorted: sortRepos(filtered, sortValue, sortKey, sortDirection) };
    } else if (memo.key !== sortKey || memo.direction !== sortDirection) {
      memo = { ...memo, key: sortKey, direction: sortDirection, sorted: sortRepos(memo.filtered, sortValue, sortKey, sortDirection) };
    }
    return memo;
  };

  // 搜索框只创建一次，重绘其他部分时不会丢失焦点。
  let timer: number | undefined;
  const search = h('input', {
    class: 'input',
    type: 'search',
    placeholder: '搜索名称、描述、话题、语言（多个词用空格分隔）',
    'aria-label': '搜索项目',
  });
  search.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => store.set({ filters: { ...store.state.filters, text: search.value } }), 150);
  });

  const summary = h('div', { class: 'summary', 'aria-live': 'polite' });
  const chips = h('div', { class: 'chips' });
  const columnMenu = h('div', { class: 'menu' });
  const tableHost = h('div', { class: 'table-wrap' });
  const pager = h('div', { class: 'pager' });

  const chip = (label: string, remove: () => void) =>
    h('button', { type: 'button', class: 'chip', 'aria-label': `移除条件 ${label}`, onclick: remove }, label);

  const drawChips = (filters: Filters) => {
    const items: Node[] = [];
    if (filters.text.trim()) {
      items.push(chip(`搜索：${filters.text.trim()}`, () => {
        search.value = '';
        store.set({ filters: { ...store.state.filters, text: '' } });
      }));
    }
    for (const node of filters.categories) {
      items.push(chip(`分类：${ctx.taxonomy?.path(node).join(PATH_SEPARATOR) ?? ''}`, () => {
        const next = new Set(store.state.filters.categories);
        next.delete(node);
        store.set({ filters: { ...store.state.filters, categories: next } });
      }));
    }
    for (const group of GROUPS) {
      for (const value of filters.selected[group.id] ?? []) {
        items.push(chip(`${group.label}：${value}`, () => {
          const next = new Set(store.state.filters.selected[group.id]);
          next.delete(value);
          store.set({ filters: { ...store.state.filters, selected: { ...store.state.filters.selected, [group.id]: next } } });
        }));
      }
    }
    const labels = { stars: 'Star', contributors: '贡献者' } as const;
    for (const key of ['stars', 'contributors'] as const) {
      const { min, max } = filters[key];
      if (min == null && max == null) continue;
      items.push(chip(`${labels[key]}：${min != null ? int(min) : ''}–${max != null ? int(max) : ''}`, () =>
        store.set({ filters: { ...store.state.filters, [key]: { min: null, max: null } } }),
      ));
    }
    mount(chips, ...items);
  };

  const drawColumnMenu = () => {
    const panel = h('div', { class: 'panel', hidden: true });
    for (const c of COLUMNS) {
      if (PINNED.includes(c.key) || !shown(c.key)) continue;
      const box = h('input', { type: 'checkbox' });
      box.checked = store.state.columns.includes(c.key);
      box.addEventListener('change', () => {
        const chosen = new Set(store.state.columns);
        if (box.checked) chosen.add(c.key);
        else chosen.delete(c.key);
        store.set({ columns: COLUMNS.map((x) => x.key).filter((k) => chosen.has(k) || PINNED.includes(k)) });
      });
      panel.append(h('label', { class: 'option', title: c.title }, box, h('span', null, c.label)));
    }
    const button = h('button', { type: 'button', class: 'btn', 'aria-haspopup': 'true', 'aria-expanded': 'false' }, '列设置');
    button.addEventListener('click', (e) => {
      e.stopPropagation();
      panel.hidden = !panel.hidden;
      button.setAttribute('aria-expanded', String(!panel.hidden));
    });
    panel.addEventListener('click', (e) => e.stopPropagation());
    mount(columnMenu, button, panel);
  };
  document.addEventListener('click', () => {
    const panel = columnMenu.querySelector<HTMLElement>('.panel');
    if (panel && !panel.hidden) {
      panel.hidden = true;
      columnMenu.querySelector('button')?.setAttribute('aria-expanded', 'false');
    }
  });

  /** 分类列只在有分类数据时显示。 */
  const shown = (key: ColumnKey) => !column(key).needsClassification || ctx.taxonomy !== null;

  const cell = (repo: Repo, key: ColumnKey): HTMLTableCellElement => {
    const col = column(key);
    const classes = [col.numeric ? 'num' : '', key === 'rank' ? 'sticky-1' : key === 'name' ? 'sticky-2' : ''].filter(Boolean).join(' ');
    if (key === 'name') {
      return h('td', { class: classes }, h('div', { class: 'repo-cell' },
        h('a', { class: 'name', href: `#/${repo.fullName}`, onclick: (e: Event) => e.stopPropagation() }, repo.fullName),
        repo.description ? h('span', { class: 'desc', title: repo.description }, truncate(repo.description, 90)) : null,
      ));
    }
    if (key === 'spark') {
      return h('td', { class: classes }, sparkline(weeksOf(ctx, repo)?.stars ?? null));
    }
    const text = col.text ? col.text(repo) : String(sortValue(repo, key) ?? '—');
    if (key === 'category') return h('td', { class: 'clip', title: text }, text);
    return h('td', { class: classes }, text);
  };

  const draw = () => {
    const { sortKey, sortDirection, page, pageSize, columns, filters } = store.state;
    const { sorted } = results();
    const view = paginate(sorted, page, pageSize);
    const keys = columns.filter(shown);

    const head = h('tr', null, keys.map((key) => {
      const col = column(key);
      const isSorted = key === sortKey;
      const classes = [col.numeric ? 'num' : '', key === 'rank' ? 'sticky-1' : key === 'name' ? 'sticky-2' : ''].filter(Boolean).join(' ');
      const th = h('th', { scope: 'col', class: classes, title: col.title, 'aria-sort': isSorted ? (sortDirection === 'asc' ? 'ascending' : 'descending') : null });
      if (col.sortValue) {
        th.append(h('button', {
          type: 'button',
          onclick: () => store.set(isSorted
            ? { sortDirection: sortDirection === 'asc' ? 'desc' : 'asc' }
            : { sortKey: key, sortDirection: col.numeric && key !== 'rank' ? 'desc' : 'asc' }),
        }, col.label + (isSorted ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : '')));
      } else th.append(col.label);
      return th;
    }));

    const body = view.items.map((repo) => {
      const tr = h('tr', null, keys.map((key) => cell(repo, key)));
      tr.addEventListener('click', () => (location.hash = `#/${repo.fullName}`));
      return tr;
    });

    mount(tableHost, view.total === 0
      ? h('p', { class: 'empty-state' }, '没有符合条件的项目')
      : h('table', null, h('thead', null, head), h('tbody', null, body)));
    // 抽屉是整个页面级别的元素；窄表头固定宽度用于 sticky 第二列偏移。
    const rank = tableHost.querySelector<HTMLElement>('th.sticky-1');
    if (rank) tableHost.style.setProperty('--rank-width', `${rank.offsetWidth}px`);

    summary.textContent = `共 ${int(view.total)} 个项目${view.total !== repos.length ? `（全部 ${int(repos.length)} 个）` : ''}`;
    drawChips(filters);

    const goto = (p: number) => store.set({ page: p });
    // 页码输入框：回车或失焦后跳转；超出范围的取最近的有效页，不是整数或为空则回到当前页。
    const jump = h('input', {
      class: 'input page-input',
      type: 'number',
      min: 1,
      max: view.pages,
      step: 1,
      inputmode: 'numeric',
      value: String(view.page),
      disabled: view.pages <= 1,
      'aria-label': `跳转到第几页（共 ${view.pages} 页）`,
    });
    jump.addEventListener('change', () => {
      const n = Math.round(Number(jump.value));
      const target = jump.value.trim() === '' || !Number.isFinite(n) ? view.page : Math.min(Math.max(1, n), view.pages);
      jump.value = String(target); // 页码没变时不会重绘，这里把输入框改回有效值
      goto(target);
    });
    const select = h('select', { 'aria-label': '每页条数' }, PAGE_SIZES.map((n) => h('option', { value: n }, `每页 ${n} 条`)));
    select.value = String(pageSize);
    select.addEventListener('change', () => store.set({ pageSize: Number(select.value) }));
    mount(pager,
      h('span', { class: 'muted' }, view.total ? `第 ${(view.page - 1) * pageSize + 1}–${Math.min(view.page * pageSize, view.total)} 条` : ''),
      h('span', { class: 'pages' },
        h('button', { type: 'button', class: 'btn', disabled: view.page <= 1, onclick: () => goto(1) }, '首页'),
        h('button', { type: 'button', class: 'btn', disabled: view.page <= 1, onclick: () => goto(view.page - 1) }, '上一页'),
        jump,
        h('span', null, `/ ${view.pages}`),
        h('button', { type: 'button', class: 'btn', disabled: view.page >= view.pages, onclick: () => goto(view.page + 1) }, '下一页'),
        h('button', { type: 'button', class: 'btn', disabled: view.page >= view.pages, onclick: () => goto(view.pages) }, '末页'),
      ),
      select,
    );
  };

  const root = h('main', { class: 'results' },
    search,
    h('div', { class: 'toolbar' }, summary, columnMenu),
    chips, tableHost, pager);
  drawColumnMenu();
  draw();
  store.subscribe((_, changed) => {
    if (['filters', 'sortKey', 'sortDirection', 'page', 'pageSize', 'columns'].some((k) => changed.has(k as never))) draw();
    // 清除全部时搜索框也要清空。
    if (changed.has('filters') && store.state.filters.text === '' && search.value !== '') search.value = '';
  });
  // 周 Star 数据到达后重绘迷你图。
  window.addEventListener('hot-repos:weeks', draw);
  return root;
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}
