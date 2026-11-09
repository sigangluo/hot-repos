import type { Theme } from '../state/prefs';

/** 把主题应用到页面；auto 时交给浏览器按系统设置决定。 */
export function applyTheme(theme: Theme): void {
  if (theme === 'auto') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

/**
 * 读取设计令牌当前生效的颜色。
 * 令牌用 light-dark() 定义，直接读变量得到的是原始文本，需要借一个元素让浏览器算出最终颜色。
 */
export function tokenColor(name: string): string {
  const probe = document.createElement('span');
  probe.style.color = `var(${name})`;
  probe.style.display = 'none';
  document.body.append(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
}
