import { loadSchemeFile } from './load';
import { buildTaxonomy, type Taxonomy } from './taxonomy';
import type { SchemeFile } from './types';

/** 加载好的分类体系：文件内容和据此建好的目录。 */
export interface SchemeData {
  file: SchemeFile;
  taxonomy: Taxonomy;
}

const cache = new Map<string, Promise<SchemeData>>();

/** 取一个分类体系；每个体系只请求一次，失败后允许再次请求。 */
export function getScheme(id: string): Promise<SchemeData> {
  let pending = cache.get(id);
  if (!pending) {
    pending = loadSchemeFile(id).then((file) => ({ file, taxonomy: buildTaxonomy(file) }));
    pending.catch(() => cache.delete(id));
    cache.set(id, pending);
  }
  return pending;
}
