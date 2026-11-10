import type { DetailColumns, Meta, RepoColumns, SchemeFile, TrendingFile, WeeksColumns } from './types';

async function getJson<T>(file: string): Promise<T> {
  const response = await fetch(`data/${file}`);
  if (!response.ok) throw new Error(`加载 ${file} 失败（HTTP ${response.status}）`);
  return (await response.json()) as T;
}

/** 首屏数据：元信息和表格所需的精简列。分类体系是附加信息，另行加载（见 schemes.ts）。 */
export async function loadCore(): Promise<[Meta, RepoColumns]> {
  return Promise.all([getJson<Meta>('meta.json'), getJson<RepoColumns>('repos.json')]);
}

/** 一个分类体系的文件（scheme-<编号>.json）。 */
export function loadSchemeFile(id: string): Promise<SchemeFile> {
  return getJson<SchemeFile>(`scheme-${id}.json`);
}

// 其余数据只请求一次，之后复用同一个 Promise。
let weeks: Promise<WeeksColumns> | undefined;
let details: Promise<DetailColumns> | undefined;

export function loadWeeks(): Promise<WeeksColumns> {
  return (weeks ??= getJson<WeeksColumns>('weeks.json'));
}

export function loadDetails(): Promise<DetailColumns> {
  return (details ??= getJson<DetailColumns>('details.json'));
}

let trending: Promise<TrendingFile> | undefined;

/** 失败后允许再次请求（页面上有“重试”按钮）。 */
export function loadTrending(): Promise<TrendingFile> {
  trending ??= getJson<TrendingFile>('trending.json').catch((error: unknown) => {
    trending = undefined;
    throw error;
  });
  return trending;
}
