import type { ClassificationFile } from './types';

/** 分类目录：节点按父在前、子在后排列，下标即 classification.json 中引用的值。 */
export interface Taxonomy {
  /** 目录附带的说明，没有则为 null。 */
  note: string | null;
  /** 一级节点，按目录顺序。 */
  roots: readonly number[];
  /** 节点的直接子节点，按目录顺序。 */
  children(node: number): readonly number[];
  /** 节点名称。 */
  label(node: number): string;
  /** 从一级到该节点的节点（含自身）。 */
  pathNodes(node: number): number[];
  /** 从一级到该节点的名称。 */
  path(node: number): string[];
  /** 形态名称。 */
  formLabel(form: number): string;
}

export function buildTaxonomy(file: ClassificationFile): Taxonomy {
  const nodes: number[][] = [];
  const children = new Map<number, number[]>();
  const roots: number[] = [];
  file.nodes.forEach(([, parent], i) => {
    if (parent < 0) roots.push(i);
    else children.set(parent, [...(children.get(parent) ?? []), i]);
    nodes[i] = parent < 0 ? [i] : [...(nodes[parent] ?? []), i];
  });
  const label = (node: number) => file.nodes[node]?.[2] ?? '';
  return {
    note: file.note,
    roots,
    children: (node) => children.get(node) ?? [],
    label,
    pathNodes: (node) => nodes[node] ?? [],
    path: (node) => (nodes[node] ?? []).map(label),
    formLabel: (form) => file.forms[form]?.[1] ?? '',
  };
}

export const PATH_SEPARATOR = ' › ';
