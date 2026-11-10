import { h } from './dom';

/** 可折叠的定义列表：标题加若干“名称：说明”。 */
export function definitions(title: string, entries: readonly [string, string][]): Node {
  return h('details', { class: 'defs' },
    h('summary', null, title),
    h('dl', null, entries.flatMap(([name, text]) => [h('dt', null, name), h('dd', null, text)])));
}

/** 分类路径：各级之间用淡色分隔符，最后一级加粗，窄时自然换行。 */
export function crumbs(path: string[]): Node {
  return h('span', { class: 'crumbs' }, path.flatMap((name, i) => [
    i > 0 ? h('i', { class: 'sep', 'aria-hidden': 'true' }, '›') : null,
    h('span', null, name),
  ]));
}

/** 键值列表里的一行。 */
export function kv(label: string, value: Node | Node[]) {
  return h('div', null, h('dt', null, label), h('dd', null, value));
}
