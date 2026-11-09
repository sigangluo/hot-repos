import { resolveReadmeUrl } from '../lib/readme-links';

/**
 * 从 GitHub 读取 README，渲染并净化。
 * README 是任何人都能写的外部内容，流程固定为：marked 转换 → DOMPurify 净化 → 改写链接与图片。
 * 不要把 marked 的输出直接放进页面。
 */
export async function loadReadme(fullName: string, path: string, signal: AbortSignal): Promise<DocumentFragment> {
  const response = await fetch(`https://raw.githubusercontent.com/${fullName}/HEAD/${path}`, { signal });
  if (!response.ok) throw new Error(`README 加载失败（HTTP ${response.status}）`);
  const markdown = await response.text();

  const [{ marked }, { default: DOMPurify }] = await Promise.all([import('marked'), import('dompurify')]);
  const html = DOMPurify.sanitize(marked.parse(markdown, { async: false, gfm: true }), { USE_PROFILES: { html: true } });

  const template = document.createElement('template');
  template.innerHTML = String(html);
  rewriteUrls(template.content, fullName);
  return template.content;
}

/** 净化之后只改写 URL 相关属性；解析不出安全地址的链接去掉 href，图片移除。 */
export function rewriteUrls(root: ParentNode, fullName: string): void {
  for (const a of root.querySelectorAll('a[href]')) {
    const url = resolveReadmeUrl(a.getAttribute('href') ?? '', fullName, 'link');
    if (url == null) a.removeAttribute('href');
    else if (url.startsWith('#')) a.setAttribute('href', url);
    else {
      a.setAttribute('href', url);
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
    }
  }
  for (const img of root.querySelectorAll('img')) {
    const src = img.getAttribute('src');
    const url = src ? resolveReadmeUrl(src, fullName, 'image') : null;
    if (url == null) img.remove();
    else {
      img.setAttribute('src', url);
      img.setAttribute('loading', 'lazy');
      img.setAttribute('referrerpolicy', 'no-referrer');
      img.removeAttribute('srcset');
    }
  }
}
