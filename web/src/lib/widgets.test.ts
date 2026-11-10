// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';
import { crumbs } from './widgets';

describe('crumbs', () => {
  it('各级用分隔符连接，最后一级是最后一个元素', () => {
    const el = crumbs(['开发', '工具']) as HTMLElement;
    expect(el.textContent).toBe('开发›工具');
    expect(el.querySelectorAll('a')).toHaveLength(0);
  });

  it('href 给出链接的那一级是链接，其余是文字', () => {
    const el = crumbs(['Programming Languages', 'vinta/awesome-python', 'Web'], (name) => (name.includes('/') ? `#/${name}` : null)) as HTMLElement;
    const links = [...el.querySelectorAll('a')];
    expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([['vinta/awesome-python', '#/vinta/awesome-python']]);
    expect(el.textContent).toBe('Programming Languages›vinta/awesome-python›Web');
  });
});
