/**
 * README 里的相对链接在 GitHub 上相对仓库根目录，页面里没有仓库文件，
 * 所以改写成 github.com / raw.githubusercontent.com 的绝对地址。
 * 只放行 http(s) 与 mailto；其他协议（如 javascript:）一律丢弃。
 */
export function resolveReadmeUrl(href: string, fullName: string, kind: 'link' | 'image'): string | null {
  if (href.startsWith('#')) return kind === 'link' ? href : null;
  const base =
    kind === 'link'
      ? `https://github.com/${fullName}/blob/HEAD/`
      : `https://raw.githubusercontent.com/${fullName}/HEAD/`;
  let url: URL;
  try {
    url = new URL(href, base);
  } catch {
    return null;
  }
  if (url.protocol === 'mailto:' && kind === 'link') return url.href;
  return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
}
