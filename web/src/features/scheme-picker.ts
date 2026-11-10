import { METHODS, UNCLASSIFIED_NOTE } from '../data/glossary';
import type { SchemeInfo } from '../data/types';
import { h } from '../lib/dom';
import { int } from '../lib/format';
import type { Ctx } from './context';
import { switchScheme } from './schemes';

/** 记住“关于这个体系”是否展开，重绘面板时不丢失。 */
const aboutOpen = new Set<string>();

/** 一个体系的说明条目：标注方式、覆盖范围、来源与许可、注意事项。筛选面板、详情和“名词与口径说明”共用。 */
export function schemeFacts(info: SchemeInfo, total: number): [string, string | Node][] {
  const [method, methodText] = METHODS[info.method];
  const facts: [string, string | Node][] = [
    ['标注方式', `${method}：${methodText}`],
    ['覆盖范围', `${int(info.classified)} / ${int(total)} 个项目有分类。${UNCLASSIFIED_NOTE}`],
  ];
  const { source } = info;
  if (source) {
    facts.push([
      '来源',
      h('span', null,
        h('a', { href: source.url, target: '_blank', rel: 'noopener noreferrer' }, source.name),
        `，许可 ${source.license}`,
        info.as_of ? `，取得于 ${info.as_of}` : ''),
    ]);
    if (source.attribution) facts.push(['署名', source.attribution]);
  }
  if (info.note) facts.push(['注意', info.note]);
  return facts;
}

/** 分类体系选择：下拉选择当前体系，下方是它的简介和“关于这个体系”。没有分类数据时不显示。 */
export function renderSchemePicker(ctx: Ctx): HTMLElement | null {
  const { meta } = ctx;
  if (meta.schemes.length === 0) return null;
  const current = ctx.scheme;
  const select = h('select', {
    class: 'input',
    id: 'scheme-select',
    onchange: (e: Event) => void switchScheme(ctx, (e.target as HTMLSelectElement).value),
  },
    ...(current ? [] : [h('option', { value: '' }, '（加载失败）')]),
    ...meta.schemes.map((s) => h('option', { value: s.id }, `${s.name}（${int(s.classified)} 个项目）`)));
  select.value = current?.id ?? '';

  const about = current
    ? h('details', { class: 'defs', open: aboutOpen.has(current.id) },
        h('summary', null, '关于这个体系'),
        h('dl', null, schemeFacts(current, meta.repos).flatMap(([term, text]) => [h('dt', null, term), h('dd', null, text)])))
    : h('p', { class: 'error' }, '分类体系加载失败，其余筛选不受影响。');
  if (current && about instanceof HTMLDetailsElement) {
    about.addEventListener('toggle', () => {
      if (about.open) aboutOpen.add(current.id);
      else aboutOpen.delete(current.id);
    });
  }

  return h('section', { class: 'scheme-pick' },
    h('label', { class: 'field-label', for: 'scheme-select' }, '分类体系'),
    select,
    current ? h('p', { class: 'def' }, current.summary) : null,
    about);
}
