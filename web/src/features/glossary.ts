import { categoryDefinition, DATA_TIMES, FACTS, RANGE_DEFINITIONS, SCHEME_TIME_TERMS, TRENDING_TERMS } from '../data/glossary';
import { h, mount } from '../lib/dom';
import { GROUPS } from '../state/query';
import { COLUMNS, type Column } from './columns';
import type { Ctx } from './context';
import { schemeFacts } from './scheme-picker';

/** 一级分类的说明最多列这么多条；更多的（如各种合集）到筛选里点 ⓘ 查看。 */
const MAX_DOMAINS = 30;

/**
 * 名词与口径说明：把页面上出现的全部名词、指标和筛选的定义集中在一处。
 * 内容来自各处声明的定义（分组、列、详情指标、分类体系），不另写一份，所以不会与它们不一致；
 * 切换分类体系时，与体系有关的部分随之更新。
 */
export function renderGlossary(ctx: Ctx): HTMLElement {
  const { meta } = ctx;
  const section = (title: string, entries: readonly [string, string | Node][]) =>
    entries.length === 0
      ? null
      : h('section', null,
          h('h3', null, title),
          h('dl', null, entries.flatMap(([term, text]) => [h('dt', null, term), h('dd', null, text)])));

  const optionList = (defs: Record<string, string>) =>
    h('ul', null, Object.entries(defs).map(([name, text]) => h('li', null, h('b', null, `${name}：`), text)));

  const build = (): (HTMLElement | null)[] => {
    const { taxonomy, scheme } = ctx;
    const filters: [string, string | Node][] = [
      ['Star 数', RANGE_DEFINITIONS.stars],
      ['贡献者数', RANGE_DEFINITIONS.contributors],
      ...GROUPS.filter((g) => g.available?.(ctx.repos) ?? true).map((g): [string, string | Node] => {
        const defs = g.optionDefinitions ?? {};
        return [g.label, h('div', null, g.definition, Object.keys(defs).length ? optionList(defs) : null)];
      }),
    ];
    if (taxonomy && scheme) filters.unshift(['分类', categoryDefinition(scheme.primary)]);

    const schemes = meta.schemes.map((s): [string, Node] => [
      s.name,
      h('div', null, s.summary,
        h('ul', null, schemeFacts(s, meta.repos, ctx.now).map(([term, text]) => h('li', null, h('b', null, `${term}：`), text)))),
    ]);
    const domains = (taxonomy?.roots ?? [])
      .map((n): [string, string] => [taxonomy!.label(n), taxonomy!.definition(n).includes ?? ''])
      .filter(([, text]) => text);

    return [
      section('数据时点', DATA_TIMES),
      meta.schemes.length ? section('分类体系', [...SCHEME_TIME_TERMS, ...schemes]) : null,
      section('筛选', filters),
      section('表格列', (COLUMNS as readonly Column[]).filter((c) => !c.needsClassification || taxonomy).map((c): [string, string] => [c.label, c.title])),
      section('项目详情', Object.entries(FACTS)),
      scheme ? section(`一级分类（${scheme.name}）`, domains.slice(0, MAX_DOMAINS)) : null,
      scheme && domains.length > MAX_DOMAINS
        ? h('p', { class: 'note' }, `共 ${domains.length} 个一级分类，其余在筛选里点分类右侧的 ⓘ 查看。`)
        : null,
      meta.trending_date ? section('近期热点', TRENDING_TERMS) : null,
    ];
  };

  const body = h('div', { class: 'glossary-body' });
  const draw = () => mount(body, ...build());
  draw();
  ctx.store.subscribe((_, changed) => changed.has('scheme') && draw());
  return h('details', { class: 'glossary' }, h('summary', null, '名词与口径说明'), body);
}
