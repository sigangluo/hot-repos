type Child = Node | string | number | null | undefined | false;
type Props = Record<string, unknown>;

/**
 * 创建 DOM 元素。文本一律作为文本节点插入——仓库名、描述、话题都是外部数据，
 * 不能拼进 innerHTML。
 *
 * h('div', { class: 'x', onclick: fn, dataset: { id: '1' } }, '文本', childNode)
 */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props?: Props | null,
  ...children: (Child | Child[])[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props ?? {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = String(value);
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2), value as EventListener);
    } else el.setAttribute(key, value === true ? '' : String(value));
  }
  el.append(...children.flat().filter((c): c is Node | string | number => c != null && c !== false).map(toNode));
  return el;
}

function toNode(child: Node | string | number): Node {
  return typeof child === 'object' ? child : document.createTextNode(String(child));
}

/** 清空容器并放入新的内容。 */
export function mount(container: Element, ...children: Child[]): void {
  container.replaceChildren(...children.filter((c): c is Node | string | number => c != null && c !== false).map(toNode));
}
