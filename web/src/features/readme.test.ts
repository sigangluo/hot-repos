// DOMPurify 官方支持 jsdom；happy-dom 的 DOM 实现与它不兼容，净化结果不可信。
// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadReadme, rewriteUrls } from './readme';

afterEach(() => vi.unstubAllGlobals());

function render(html: string): HTMLElement {
  const root = document.createElement('div');
  root.innerHTML = html;
  rewriteUrls(root, 'o/r');
  return root;
}

describe('rewriteUrls', () => {
  it('相对链接和图片改写为 GitHub 地址，外部链接在新标签页打开', () => {
    const root = render('<a href="docs/a.md">a</a><a href="https://x.dev">x</a><a href="#top">t</a><img src="img/p.png">');
    const [rel, ext, anchor] = [...root.querySelectorAll('a')];
    expect(rel?.getAttribute('href')).toBe('https://github.com/o/r/blob/HEAD/docs/a.md');
    expect(ext?.getAttribute('rel')).toBe('noopener noreferrer');
    expect(ext?.getAttribute('target')).toBe('_blank');
    expect(anchor?.getAttribute('target')).toBeNull();
    const img = root.querySelector('img');
    expect(img?.getAttribute('src')).toBe('https://raw.githubusercontent.com/o/r/HEAD/img/p.png');
    expect(img?.getAttribute('referrerpolicy')).toBe('no-referrer');
  });

  it('不安全的地址：链接去掉 href，图片整个移除', () => {
    const root = render('<a href="javascript:alert(1)">x</a><img src="data:image/svg+xml;base64,AAAA"><img>');
    expect(root.querySelector('a')?.hasAttribute('href')).toBe(false);
    expect(root.querySelectorAll('img')).toHaveLength(0);
  });
});

describe('loadReadme', () => {
  const evil = [
    '# Title',
    '<script>window.pwned = 1</script>',
    '<img src="x.png" onerror="window.pwned = 2">',
    '<a href="javascript:window.pwned = 3">click</a>',
    '<iframe src="https://evil.example"></iframe>',
    '<div onclick="window.pwned = 4">div</div>',
    '[guide](docs/guide.md) ![logo](img/logo.png)',
  ].join('\n\n');

  it('净化危险内容，并改写保留下来的链接', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(evil)));
    const content = await loadReadme('o/r', 'README.md', new AbortController().signal);
    const box = document.createElement('div');
    box.append(content);
    expect(box.querySelector('script, iframe')).toBeNull();
    expect(box.innerHTML).not.toMatch(/onerror|onclick|javascript:/i);
    expect(box.querySelector('h1')?.textContent).toBe('Title');
    expect(box.querySelector('a[href$="docs/guide.md"]')?.getAttribute('href')).toBe(
      'https://github.com/o/r/blob/HEAD/docs/guide.md',
    );
    expect(box.querySelector('img[src*="logo.png"]')?.getAttribute('src')).toBe(
      'https://raw.githubusercontent.com/o/r/HEAD/img/logo.png',
    );
    expect((globalThis as { pwned?: number }).pwned).toBeUndefined();
  });

  it('请求失败时抛出带状态码的错误', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 404 })));
    await expect(loadReadme('o/r', 'README.md', new AbortController().signal)).rejects.toThrow('404');
  });

  it('请求的是仓库默认分支上的文件', async () => {
    const fetchMock = vi.fn(async (_url: string) => new Response('x'));
    vi.stubGlobal('fetch', fetchMock);
    await loadReadme('o/r', 'readme.md', new AbortController().signal);
    expect(fetchMock.mock.calls[0]?.[0]).toBe('https://raw.githubusercontent.com/o/r/HEAD/readme.md');
  });
});
