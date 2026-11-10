import { METHODS } from '../data/glossary';
import { placement, type Placement, type Repo } from '../data/model';
import { getScheme, type SchemeData } from '../data/schemes';
import type { DetailColumns, SchemeInfo } from '../data/types';
import { h, mount } from '../lib/dom';
import { crumbs, definitions, kv } from '../lib/widgets';
import type { Ctx } from './context';

/** 一个体系对这个项目的分类：没有标注时为 null。 */
interface Entry {
  info: SchemeInfo;
  data: SchemeData;
  place: Placement;
}

const labeled = (p: Placement) => p.category.length > 0 || p.relatedPaths.length > 0;

/** “分类与形态的含义”：主分类（或各分类）收什么、不收什么，以及该项目各形态的定义。 */
function meaning({ data, place }: Entry): Node | null {
  const { taxonomy } = data;
  const entries: [string, string][] = [];
  for (const node of place.category.length ? place.leaves.slice(0, 1) : place.leaves) {
    const { includes, excludes } = taxonomy.definition(node);
    const name = taxonomy.label(node);
    if (includes) entries.push([`${name}：收`, includes]);
    if (excludes) entries.push([`${name}：不收`, excludes]);
  }
  const byLabel = new Map(taxonomy.forms.map((f) => [f.label, f.definition]));
  for (const form of place.forms) {
    const text = byLabel.get(form);
    if (text) entries.push([form, text]);
  }
  return entries.length ? definitions('分类与形态的含义', entries) : null;
}

function card(entry: Entry, text: { summary: string | null; review: string | null }): HTMLElement {
  const { info, place } = entry;
  const [method] = METHODS[info.method];
  return h('section', { class: 'card' },
    h('h3', null, `分类 · ${info.name}`, ' ', h('span', { class: 'chip plain' }, method)),
    text.summary ? h('p', { class: 'class-summary' }, text.summary) : null,
    h('dl', { class: 'kv-list' },
      place.category.length ? kv('主分类', crumbs(place.category)) : null,
      place.relatedPaths.length
        ? kv(info.primary ? '关联分类' : '分类', h('div', { class: 'paths' }, place.relatedPaths.map(crumbs)))
        : null,
      place.forms.length
        ? kv('项目形态', h('div', { class: 'chips' }, place.forms.map((f) => h('span', { class: 'chip plain' }, f))))
        : null),
    meaning(entry),
    text.review ? h('p', { class: 'note' }, `标记为待复核：${text.review}`) : null,
    info.source
      ? h('p', { class: 'note' }, '来源：',
          h('a', { href: info.source.url, target: '_blank', rel: 'noopener noreferrer' }, info.source.name),
          `（${info.source.license}）`)
      : null);
}

/**
 * 详情里的分类：当前体系排在最前（项目没被收录时说明一声），其余体系只在收录了这个项目时才显示——
 * 这样可以对照不同的人是怎么分这个项目的。体系文件和详情数据到达后才画出来。
 */
export function schemeCards(ctx: Ctx, repo: Repo, details: Promise<DetailColumns | null>): HTMLElement {
  const host = h('div', { class: 'scheme-cards' });
  const { schemes } = ctx.meta;
  if (schemes.length === 0) return host;
  void Promise.all([
    Promise.all(schemes.map((info) => getScheme(info.id).then((data): Entry => ({ info, data, place: placement(data.file, data.taxonomy, repo.index) }), () => null))),
    details,
  ]).then(([loaded, d]) => {
    if (!host.isConnected) return;
    const entries = loaded.filter((e): e is Entry => e !== null);
    const current = entries.find((e) => e.info.id === ctx.scheme?.id);
    const shown = [...(current ? [current] : []), ...entries.filter((e) => e !== current && labeled(e.place))];
    mount(host, ...shown.map((entry) => {
      if (!labeled(entry.place)) {
        return h('section', { class: 'card' }, h('h3', null, `分类 · ${entry.info.name}`), h('p', { class: 'muted' }, '这个体系没有收录该项目。'));
      }
      const text = d?.scheme_text[entry.info.id];
      return card(entry, { summary: text?.summary[repo.index] ?? null, review: text?.review_reason[repo.index] ?? null });
    }));
  });
  return host;
}
