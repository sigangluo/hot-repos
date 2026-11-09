# 前端说明

`web/` 是纯静态看板，用 Vite + TypeScript 构建，没有 UI 框架。只读 `data/` 导出的页面数据，不依赖采集代码（见 [architecture.md](architecture.md)）。

## 数据加载

`hot-repos export` 生成列式 JSON，页面分层加载（见 `src/data/load.ts`）：

| 文件 | 内容 | 何时加载 |
|---|---|---|
| `meta.json` | 快照日期、各部分获取时间、数量、最新 Trending 快照日期（`trending_date`，为空则不显示“近期热点”） | 首屏 |
| `repos.json` | 表格、筛选、搜索所需的精简列 | 首屏 |
| `classification.json` | 分类目录和每个项目的主分类、关联分类、形态（与 `repos.json` 行对齐）；没有分类数据时不生成 | 首屏，在 `meta.json` 之后请求；失败时页面照常显示，只是没有分类 |
| `weeks.json` | 官方周 Star 分布 | 首屏渲染后，用于迷你图；打开详情时复用 |
| `details.json` | 语言构成、赞助链接、README 文件名、分类的简介与复核原因等 | 首次打开详情时 |
| `trending.json` | 最新一天的 Trending 快照；还没有快照时不生成，页面也不显示“近期热点” | 首次切到“近期热点”时，失败可重试 |

页面类型在 `src/data/types.ts`，与 `src/hot_repos/export_web.py` 的列一一对应，由 `tests/test_export.py` 检查一致。**改导出的列时，先改 `export_web.py`，再改 `types.ts`，测试会提醒遗漏。**

README 正文不在数据里，查看详情时从 `raw.githubusercontent.com/{项目}/HEAD/{文件名}` 读取，需要联网。

## 模块

| 目录 | 职责 |
|---|---|
| `src/main.ts` | 入口：加载数据、组装页面；地址对应页面状态，可直接分享：`#/trending` 近期热点，`#/owner/repo` 项目详情，空地址为总榜 |
| `src/data/` | 类型、分层加载、把列式数据还原为行并派生字段（`model.ts`）、分类目录（`taxonomy.ts`） |
| `src/state/` | `store.ts` 状态容器；`query.ts` 筛选、排序、分页（纯函数）；`prefs.ts` 本地偏好；`route.ts` 地址与视图的对应；`trending.ts` 把快照整理成（时间段，语言）榜单并标出已在总榜的项目 |
| `src/features/` | 页面各部分：`header`、`filters`、`table`、`trending`、`drawer`、`readme`、`sparkline`、`position`、`columns` |
| `src/charts/` | ECharts 按需注册（`echarts.ts`）与周 Star 图 |
| `src/lib/` | `dom`（建元素）、`format`、`theme`、`readme-links` |
| `src/styles/` | `tokens.css` 设计令牌、`base.css`、`components.css` |

**状态流**：`Store.set(patch)` 更新状态，通知订阅者并带上变化的字段集合，订阅者只重绘自己关心的部分。筛选、排序、每页条数变化后自动回到第一页。主题、列、每页条数保存在 `localStorage`（键前缀 `hot-repos:`），保存的值不合法或列已不存在时忽略。

**纯函数与界面分离**：筛选、排序、分页、分桶、位置计算都在不碰 DOM 的纯函数里，测试直接覆盖。

## 分类

数据里有分类时（`meta.classified` 大于 0 且 `classification.json` 加载成功），页面多出：

- **分类树**（`features/category-filter.ts`）：一棵可展开的树，最多三级，每一级都可勾选；勾选某一级就包含其下全部子分类，多个勾选取并集。选中子分类时，未选的父级显示半选并自动展开；选中一个节点时，它的上级和下级的单独勾选被收起（上级被收窄，下级已被包含）。数量是“满足其他全部条件”时该分类下的项目数，没有项目的分支隐藏（已选的除外），分类自身的勾选不影响自己的数量。树上方有“仅主分类 / 含关联分类”切换：默认只按主分类，每个项目只出现一次，各级数量可以相加；切到“含关联分类”后，项目也出现在它的关联分类下。没有分类的项目在勾选任何分类后不会出现。树的上方显示目录的 `note`（若有）。逻辑在 `state/query.ts`（`categoryCounts` 与筛选条件 `categories`、`categoryScope`），目录结构在 `data/taxonomy.ts`。
- **项目形态**：与话题等一样，是 `GROUPS` 里的一个普通分组。
- **表格列**“分类”：主分类的完整路径，过长时省略，悬停看全文，可排序，默认显示。
- **详情卡片**：一句话简介、主分类、关联分类、项目形态、待复核原因和目录的 `note`（若有）；未分类的项目显示“尚未分类”。简介与复核原因来自 `details.json`，随详情数据到达后补上。
- **搜索**：搜索文本包含分类名称和形态。

没有分类数据（文件不存在或加载失败）时，上述分类相关的筛选、列内容和卡片都不出现，页面其余部分不受影响。

## 近期热点

与 GitHub Trending 对应：今日、本周、本月三个时间段加语言筛选，每条显示简介、语言、Star、Fork、该时间段新增 Star 和页面上标注的贡献者头像。项目已在总榜中时标出总榜名次并打开站内详情，否则链接到 GitHub（新窗口）。页面只展示最新一天的快照，历史快照留在 `data/trending/`，历史功能尚未做。

- 视图由 `store.state.view` 决定，总榜和近期热点是同一页面里的两个区域，切换时一个隐藏、一个显示，总榜的筛选和翻页状态保留。
- 从近期热点打开详情，关闭后回到 `#/trending`；浏览器前进后退可用。
- 头像直接引用 `github.com/<用户名>.png`，需要联网；加载失败只是不显示头像。

## 常见改动

- **加一列**：在 `features/columns.ts` 的 `COLUMNS` 里加一项（键、标题、排序取值、显示文本）；需要新的取值时在 `data/model.ts` 的 `Repo` 里加字段。
- **加一个筛选组**：在 `state/query.ts` 的 `GROUPS` 里加一项，声明 `values(repo)` 返回该项目在此组的取值；选项数量、已选条件标签和清除都自动生效。
- **改颜色、字号、间距**：只改 `styles/tokens.css`。组件样式里不写死数值；明暗两套值用 `light-dark()` 写在同一行。需要在 JS 里取令牌颜色（如图表）用 `lib/theme.ts` 的 `tokenColor()`。

## README 渲染与安全

README 是任何人都能写的外部内容。流程固定为 **marked 转换 → DOMPurify 净化 → 改写链接与图片**（`features/readme.ts`），不要把 marked 的输出直接放进页面。

- 相对链接改写为 `github.com/.../blob/HEAD/...`，相对图片改写为 `raw.githubusercontent.com/.../HEAD/...`；只放行 http(s)（链接另放行 mailto），其他协议的链接去掉 `href`，图片移除。外部链接带 `noopener noreferrer`，图片不带 Referrer。
- 构建时（`vite.config.ts` 的插件）给页面注入内容安全策略：脚本只能来自本站（`index.html` 里提前应用主题的内联脚本用哈希放行，脚本改动后哈希自动重算），请求只允许本站和 `raw.githubusercontent.com`，禁用 `object`、表单提交。开发服务器不注入，以免影响热更新。
- 页面其余部分的外部数据（项目名、描述、话题）一律以文本节点插入，不拼 HTML。

## 性能

首屏只加载约 14KB（gzip）脚本、3KB 样式和 `meta.json` + `repos.json`（5000 个项目约 0.7MB gzip）。ECharts（约 175KB gzip）、marked、DOMPurify 在首次打开详情或 README 时才加载。筛选与排序在 5000 行上同步完成；表格只渲染当前页。

线上页面（近期热点视图）的 Lighthouse，桌面与移动均为：可访问性 100、最佳实践 100、SEO 100。

## 测试

```bash
cd web && npm test
```

- 纯逻辑（筛选、排序、分页、格式化、位置计算、链接改写）直接测。
- 界面部分（表格、状态容器、迷你图）用 happy-dom 做渲染测试。
- **README 净化的测试必须用 jsdom**（测试文件顶部已声明）：happy-dom 与 DOMPurify 不兼容，净化结果不可信。

## 已知限制

- 不能用 `file://` 打开，需要 HTTP（`npm run dev` / `npm run preview` 或部署后访问）。
- README 里的长表格只做横向滚动，不分页。
- 表格数值列没有数据条。
- 近期热点只展示最新一天；头像来自 github.com，CSP 的 `img-src` 已允许 https 图片。
