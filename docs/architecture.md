# 架构与项目结构

本文是项目结构的约定。目录职责、依赖方向和数据流变更时，先改这里再改代码。

## 目标

采集 GitHub 总 Star 榜 Top N 项目的元数据和官方 Star 时间分布，保存为 Parquet，并发布一个可检索、可筛选的静态看板（GitHub Pages）。

三层分工，互不越界：

| 层 | 职责 | 位置 |
|---|---|---|
| 采集与整理 | 调 GitHub API，清洗成规范数据 | `src/hot_repos/` |
| 数据 | 唯一事实来源，随仓库提交 | `data/` |
| 展示 | 只读数据，不回写，不依赖采集代码 | `web/` |

数据流单向：`GitHub API → .cache/（原始响应）→ data/（规范数据）→ web/public/data/（页面数据）→ 静态站点`。

## 目录结构

```
hot-repos/
├── README.md                  项目介绍、快速开始
├── LICENSE
├── pyproject.toml             Python 包、依赖、ruff / pytest 配置（uv 管理）
├── uv.lock
├── .python-version
├── .github/workflows/
│   ├── ci.yml                 Python 与前端的检查和测试
│   ├── pages.yml              由 data/ 生成页面数据、构建并部署到 GitHub Pages
│   └── trending.yml           每天抓取 Trending 快照并提交到 data/trending/
├── docs/
│   ├── architecture.md        本文
│   ├── data-model.md          数据文件、字段、口径、质量约束
│   ├── operations.md          抓取、续跑、限流、缓存、页面开发的操作手册
│   ├── frontend.md            前端结构、加载方式、常见改动、安全与测试
│   └── deployment.md          GitHub Pages 部署、数据更新、发布前检查清单
├── src/hot_repos/             Python 包（src 布局）
│   ├── cli.py                 命令入口：fetch / trending / validate / export
│   ├── config.py              路径与常量，唯一的配置来源
│   ├── schema.py              Parquet 表结构，数据契约的唯一定义
│   ├── cache.py               原子写 JSON、带时间戳的缓存、追加式日志（断点续跑）
│   ├── collect.py             带缓存的批量并发抓取
│   ├── github/
│   │   ├── client.py          HTTP 客户端：重试、限流等待、请求节流
│   │   ├── search.py          总榜搜索（按 Star 区间分段，绕开 1000 条上限）
│   │   ├── graphql.py         批量元数据查询
│   │   ├── contributors.py    贡献者数量
│   │   ├── star_weeks.py      官方周 Star 分布
│   │   └── trending.py        Trending 网页的抓取与解析（无接口，解析 HTML）
│   ├── transform.py           API 响应 → 规范行（纯函数，无 IO）
│   ├── store.py               读写 data/，合并历史名次，发布
│   ├── trending.py            Trending 每日快照：整天采集、写入、读取
│   ├── export_web.py          data/ → web/public/data/（列式 JSON）
│   ├── pipeline.py            采集流程编排：抓取 → 组装 → 校验 → 发布
│   └── validate.py            数据完整性与一致性检查
├── tests/                     与 src 对应；网络一律用桩，不访问真实 API
├── data/                      规范数据，提交到 git
│   ├── repos.parquet          当前快照，一行一个项目
│   ├── star_weeks.parquet     官方周 Star 分布
│   ├── rank_history.parquet   各快照日期的总榜名次
│   ├── manifest.json          快照日期、运行参数、改名与缺失记录
│   └── trending/              Trending 每日快照，一天一个 YYYY-MM-DD.parquet，只追加
├── .cache/                    原始 API 响应与断点，不提交
└── web/                       静态看板（Vite + TypeScript，无框架）
    ├── package.json  vite.config.ts  tsconfig.json  index.html
    ├── public/data/           页面数据，由 export 生成，不提交
    └── src/
        ├── main.ts            入口：加载数据、组装页面、地址 `#/owner/repo` 对应详情
        ├── data/              types.ts（页面数据类型）、load.ts（分层加载）、model.ts（行模型与派生字段）
        ├── state/             store.ts（状态容器）、query.ts（筛选/排序/分页，纯函数）、prefs.ts（本地偏好）
        ├── features/          header / filters / table / trending / drawer / readme / sparkline / columns
        ├── charts/            echarts.ts（按需注册）、star-chart.ts
        ├── lib/               dom、format、theme、readme-links
        └── styles/            tokens.css（设计令牌）、base.css、components.css
```

## 依赖方向

- `web/` 不 import Python；与采集层之间只有 `data/` 里的文件格式这一个接口。
- `github/*` 只负责取数据并返回原始结构；字段映射在 `transform.py`，落盘在 `store.py`。
- `transform.py` 为纯函数，不发请求、不读写文件，方便测试。
- 命令之间不互相调用脚本；公共逻辑一律放包内模块。
- 常量（路径、阈值、并发数）只在 `config.py` 定义，不在各处重复。

## 关键设计决定

1. **数据契约单点定义**：Parquet 结构只在 `schema.py` 定义；`docs/data-model.md`、导出、校验都以它为准。列表、嵌套数据（话题、语言、赞助链接）使用 Parquet 原生 list / struct，不存 JSON 字符串。
2. **不存冗余列**：不保存取值恒定的列，也不保存可由其他列推出的列；当前快照只有一份，历史名次单独成表。
3. **README 不入库**：采集阶段只记录 README 的路径，不下载正文；页面按需从 `raw.githubusercontent.com` 读取。仓库体积保持在数 MB，历史干净。README 经 marked 渲染后必须再过 DOMPurify。
4. **采集缓存与规范数据分离**：`.cache/` 可随时删除并重建，`data/` 才是成果。
5. **原子与可续跑**：所有落盘先写临时文件再替换；长任务按批追加日志，中断后重跑只补缺口。
6. **前端依赖走 npm**：不手工放置压缩后的第三方文件；ECharts 按需引入以控制体积。
7. **页面数据分层加载**：导出为列式 JSON（`trending.json` 仅在有 Trending 快照时生成）（`{列名: [值]}`，各列等长、按名次排序），不拆成每项目一个文件。首屏只加载 `meta.json` 和 `repos.json`（5000 项目约 1.9MB，gzip 后约 0.7MB）；`weeks.json`（周 Star，迷你图和详情用）在首屏之后加载，`details.json`（语言构成、赞助链接等）在首次打开详情时加载，`trending.json` 在首次切到“近期热点”时加载。时间戳统一为 Unix 秒。首屏体积是性能预算的第一项。
8. **页面通过 HTTP 访问**：使用 ES 模块，本地用 `npm run dev` / `npm run preview`，不再支持双击 `file://` 打开。
9. **视觉统一**：颜色、间距、字号、圆角集中为 CSS 变量（设计令牌），明暗主题只切换令牌，组件样式不写死颜色值。
10. **README 外部内容的两道防线**：净化（DOMPurify）加内容安全策略（构建时注入，脚本只能来自本站）。
11. **Trending 是独立的数据源**：它来自网页解析，不是接口，更新频率（每天）和总榜（低频）不同，所以不进总榜的整体发布流程，也不共用 `manifest.json`。按日期分文件、只追加，历史无法补抓，因此采集器先于页面完成并开始积累。快照要么完整要么不写，解析遇到结构变化报错而不是猜测。采集请求不带 Token。
12. **测试分层**：Python 侧网络一律用内存中的假 GitHub，另有对真实 GitHub 的人工验证（采集过程中暴露过假数据测不到的问题，如 200 响应体不是 JSON）；前端纯逻辑直接测，界面用 happy-dom，README 净化用 jsdom。

## 范围外

项目分类、榜单对比、趋势预测等不属于当前范围；Trending 的页面展示与历史查询见下方实施顺序。需要时作为独立功能先写设计再加入，不为其预留空目录或空接口。

## 实施顺序

1. ~~项目结构与仓库基础~~ 已完成
2. ~~数据契约：`schema.py`、`docs/data-model.md`、`config.py`、`validate.py`~~ 已完成
3. ~~已有快照迁入 `data/` 并通过 `validate`~~ 已完成
4. ~~采集层：`github/*`、`cache.py`、`collect.py`、`transform.py`、`store.py`、`pipeline.py`、`cli.py`，附测试~~ 已完成
5. ~~导出层（`export_web.py`）与前端：设计令牌 → 数据加载 → 表格 → 筛选 → 详情 → README~~ 已完成
6. ~~CI 与 Pages 工作流、文档~~ 已完成；工作流尚未在 GitHub 上运行。LICENSE 与首次提交待定，见 [deployment.md](deployment.md)
7. Trending：~~采集器、每日快照、校验、每日定时任务~~ 已完成；~~页面（与 Trending 对齐的"近期热点"视图）~~ 已完成；自动部署联动与历史功能（按日期回看、上榜天数与最高名次、详情中的上榜时间线）待做，历史功能需要先积累数据
