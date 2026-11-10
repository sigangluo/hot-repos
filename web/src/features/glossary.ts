import { CATEGORY_DEFINITION, DATA_TIMES, FACTS, RANGE_DEFINITIONS, TRENDING_TERMS } from '../data/glossary';
import { h } from '../lib/dom';
import { GROUPS } from '../state/query';
import { COLUMNS, type Column } from './columns';
import type { Ctx } from './context';

/**
 * 名词与口径说明：把页面上出现的全部名词、指标和筛选的定义集中在一处。
 * 内容来自各处声明的定义（分组、列、详情指标、分类目录），不另写一份，所以不会与它们不一致。
 */
export function renderGlossary(ctx: Ctx): HTMLElement {
  const { taxonomy, meta } = ctx;
  const section = (title: string, entries: readonly [string, string | Node][]) =>
    entries.length === 0
      ? null
      : h('section', null,
          h('h3', null, title),
          h('dl', null, entries.flatMap(([term, text]) => [h('dt', null, term), h('dd', null, text)])));

  const optionList = (defs: Record<string, string>) =>
    h('ul', null, Object.entries(defs).map(([name, text]) => h('li', null, h('b', null, `${name}：`), text)));

  const filters: [string, string | Node][] = [
    ['Star 数', RANGE_DEFINITIONS.stars],
    ['贡献者数', RANGE_DEFINITIONS.contributors],
    ...GROUPS.filter((g) => g.available?.(ctx.repos) ?? true).map((g): [string, string | Node] => {
      const defs = typeof g.optionDefinitions === 'function' ? g.optionDefinitions(taxonomy) : (g.optionDefinitions ?? {});
      return [g.label, h('div', null, g.definition, Object.keys(defs).length ? optionList(defs) : null)];
    }),
  ];
  if (taxonomy) filters.unshift(['分类', CATEGORY_DEFINITION]);

  const domains: [string, string][] = taxonomy
    ? taxonomy.roots.map((n): [string, string] => [taxonomy.label(n), taxonomy.definition(n).includes ?? ''])
    : [];

  return h('details', { class: 'glossary' },
    h('summary', null, '名词与口径说明'),
    h('div', { class: 'glossary-body' },
      section('数据时点', DATA_TIMES),
      section('筛选', filters),
      section('表格列', (COLUMNS as readonly Column[]).filter((c) => !c.needsClassification || taxonomy).map((c): [string, string] => [c.label, c.title])),
      section('项目详情', Object.entries(FACTS)),
      section('一级分类', domains),
      meta.trending_date ? section('近期热点', TRENDING_TERMS) : null));
}
