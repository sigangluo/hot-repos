import { createHash } from 'node:crypto';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

/**
 * 构建时给页面加内容安全策略（CSP）。
 * README 来自任何人写的仓库，除了 DOMPurify 净化，再用 CSP 限制脚本只能来自本站，
 * 并只允许向本站和 raw.githubusercontent.com 发请求。
 * index.html 里用于提前应用主题的内联脚本，用哈希放行，改动脚本后哈希自动重算。
 * 只在构建时注入，避免影响开发服务器的热更新。
 */
function contentSecurityPolicy(): Plugin {
  return {
    name: 'content-security-policy',
    apply: 'build',
    transformIndexHtml(html) {
      const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(
        (m) => `'sha256-${createHash('sha256').update(m[1] ?? '').digest('base64')}'`,
      );
      const policy = [
        "default-src 'self'",
        `script-src 'self' ${inline.join(' ')}`.trim(),
        // ECharts 与页面内的少量行内 style 需要 'unsafe-inline'；脚本不受影响。
        "style-src 'self' 'unsafe-inline'",
        // README 里的图片可能来自任意 https 站点。
        "img-src 'self' data: https:",
        "connect-src 'self' https://raw.githubusercontent.com",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'none'",
      ].join('; ');
      return html.replace('</title>', `</title>\n    <meta http-equiv="Content-Security-Policy" content="${policy}" />`);
    },
  };
}

// 部署到 GitHub Pages 的子路径时用相对路径，本地与任意仓库名都能工作。
export default defineConfig({
  base: './',
  plugins: [contentSecurityPolicy()],
  build: { target: 'es2022', sourcemap: false },
  test: { include: ['src/**/*.test.ts'] },
});
