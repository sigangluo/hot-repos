import type { ClassificationFile, DetailColumns, Meta, RepoColumns, TrendingFile, WeeksColumns } from './types';

async function getJson<T>(file: string): Promise<T> {
  const response = await fetch(`data/${file}`);
  if (!response.ok) throw new Error(`加载 ${file} 失败（HTTP ${response.status}）`);
  return (await response.json()) as T;
}

/**
 * 首屏数据：元信息、表格所需的精简列，以及分类（若有）。
 * 分类是附加信息：加载失败时页面照常显示，只是没有分类筛选与分类列。
 */
export async function loadCore(): Promise<[Meta, RepoColumns, ClassificationFile | null]> {
  const [meta, repos] = await Promise.all([getJson<Meta>('meta.json'), getJson<RepoColumns>('repos.json')]);
  const classification = meta.classified > 0
    ? await getJson<ClassificationFile>('classification.json').catch(() => null)
    : null;
  return [meta, repos, classification];
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
