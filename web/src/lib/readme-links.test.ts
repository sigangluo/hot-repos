import { describe, expect, it } from 'vitest';
import { resolveReadmeUrl } from './readme-links';

const repo = 'owner/repo';

describe('resolveReadmeUrl', () => {
  it('相对链接指向仓库的 blob 页面，相对图片指向 raw 地址', () => {
    expect(resolveReadmeUrl('docs/guide.md', repo, 'link')).toBe('https://github.com/owner/repo/blob/HEAD/docs/guide.md');
    expect(resolveReadmeUrl('./img/a.png', repo, 'image')).toBe('https://raw.githubusercontent.com/owner/repo/HEAD/img/a.png');
    expect(resolveReadmeUrl('/LICENSE', repo, 'link')).toBe('https://github.com/LICENSE');
  });

  it('绝对地址原样保留', () => {
    expect(resolveReadmeUrl('https://example.com/x?y=1', repo, 'link')).toBe('https://example.com/x?y=1');
    expect(resolveReadmeUrl('http://example.com/a.png', repo, 'image')).toBe('http://example.com/a.png');
  });

  it('页内锚点只对链接有效', () => {
    expect(resolveReadmeUrl('#install', repo, 'link')).toBe('#install');
    expect(resolveReadmeUrl('#install', repo, 'image')).toBeNull();
  });

  it('丢弃危险协议', () => {
    expect(resolveReadmeUrl('javascript:alert(1)', repo, 'link')).toBeNull();
    expect(resolveReadmeUrl('data:text/html;base64,AAAA', repo, 'image')).toBeNull();
    expect(resolveReadmeUrl('vbscript:x', repo, 'link')).toBeNull();
  });

  it('mailto 只允许用于链接', () => {
    expect(resolveReadmeUrl('mailto:a@b.c', repo, 'link')).toBe('mailto:a@b.c');
    expect(resolveReadmeUrl('mailto:a@b.c', repo, 'image')).toBeNull();
  });
});
