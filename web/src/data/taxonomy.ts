import type { SchemeFile } from './types';

/** 一个分类体系的目录：节点按父在前、子在后排列，下标即体系文件中引用的值。 */
export interface Taxonomy {
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
  /** 节点的收录说明与排除说明；没有则为 null。 */
  definition(node: number): { includes: string | null; excludes: string | null };
  /** 全部节点都是一级（没有层级）。 */
  flat: boolean;
}

export function buildTaxonomy(file: SchemeFile): Taxonomy {
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
    roots,
    flat: roots.length === file.nodes.length,
    children: (node) => children.get(node) ?? [],
    label,
    pathNodes: (node) => nodes[node] ?? [],
    path: (node) => (nodes[node] ?? []).map(label),
    definition: (node) => ({ includes: file.nodes[node]?.[3] ?? null, excludes: file.nodes[node]?.[4] ?? null }),
  };
}

export const PATH_SEPARATOR = ' › ';
