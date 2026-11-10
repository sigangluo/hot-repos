# hot-repos

采集 GitHub 总 Star 榜 Top N 项目的元数据和官方 Star 时间分布，输出为 Parquet，并提供可检索、可筛选的静态看板。

> 状态：采集、校验和看板均已可用，已部署到 <https://sigangluo.github.io/hot-repos/>，部署与每日任务见 [docs/deployment.md](docs/deployment.md)。

## 功能

- **采集**：总榜（按 Star 区间分段，绕开搜索接口 1000 条上限）、仓库元数据、贡献者数、官方周 Star 分布。可中断续跑，自动应对限流和临时错误。
- **近期热点**：每天抓取 GitHub Trending（全部语言和 10 种主流语言，日、周、月三个时间段）并按日保存，看板里按 Trending 的方式展示，已在总榜的项目可直接看详情；历史快照留作后续的历史功能。
- **分类体系（可选）**：看板里可以切换多套分类体系，按分类树（任意一级）筛选，详情里并排显示各体系怎么分这个项目。除本站自己的分类（语言模型判断，目前只覆盖创建不足一年的 361 个项目，尚未经人工验证）外，还接入了别人已经做好的公开分类：GitHub Explore 主题合集、OSS Insight 项目合集、Borges 等的人工分类、CNCF 与 LF AI 的 Landscape，只记录“哪个项目属于哪一类”并注明出处与许可，不重新标注。见 [docs/schemes.md](docs/schemes.md)。
- **数据**：三张 Parquet 表加一个清单文件，字段、口径和一致性约束有文档，采集结果先校验再发布。
- **看板**：搜索，分类树、项目形态、语言、许可证、话题等 10 组筛选（选项旁显示数量），Star 与贡献者范围，可排序、可选列的表格，近 30 周迷你图，项目详情（基本信息、分类、总榜位置、周 Star 图、语言构成、README），明暗主题。

## 环境

- Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)
- Node.js 22+（只有看板开发和构建需要）
- GitHub Token：环境变量 `GITHUB_TOKEN`，或已登录的 `gh`。只请求公开数据，Token 只在内存中使用。

## 快速开始

```bash
uv sync
uv run hot-repos fetch --top 5000     # 采集并更新 data/，可中断，重跑续上
uv run hot-repos trending             # 抓取今天的 Trending 快照，写入 data/trending/
uv run hot-repos validate             # 校验 data/
```

查看看板：

```bash
uv run hot-repos export               # 由 data/ 生成页面数据
cd web && npm ci && npm run dev       # 开发服务器
```

页面需要通过 HTTP 访问，不能双击 `index.html` 打开。

## 数据

`data/` 包含当前快照的项目元数据、官方周 Star 分布、历次快照的名次，以及 `data/trending/` 下每天一个文件的 Trending 快照。可选的分类体系在 `data/schemes/<编号>/`（`scheme.json`、`labels.parquet`），每个体系只覆盖一部分项目。用 DuckDB 读取的例子：

```bash
uv run --with duckdb python -c "
import duckdb
duckdb.sql(\"select rank, full_name, stars from 'data/repos.parquet' order by rank limit 10\").show()
"
```

使用前请了解口径，详见 [docs/data-model.md](docs/data-model.md)：

- Star 总数是累计规模，不表示近期增长速度。
- 周 Star 分布统计的是采集时仍保留的 Star 按创建时间的分布，已取消的 Star 不在其中，不能据此还原历史净增长。
- 总榜是一次采集快照，不是事务一致的时点排名；排名和元数据的获取时间不同，各自记录。
- Trending 数据来自解析网页，历史只能从开始采集那天算起，无法补抓。
- 本站分类由语言模型判断，未经人工验证，只覆盖总榜中创建不足一年的 361 个项目，这批项目高度集中在智能体生态，不能代表整个总榜。外部体系是别人做的分类，各自只收录一部分项目，没被收录不代表不属于那一类；其中 Borges 的数据是 2017 年的。每个体系的标注方式、覆盖数、来源与许可在页面的“关于这个体系”里。

## 项目结构

```
src/hot_repos/   采集、校验、导出（Python 包）
tests/           测试，网络一律用内存中的假 GitHub
data/            规范数据，提交到 git
web/             静态看板（Vite + TypeScript）
docs/            文档
```

## 文档

- [架构与项目结构](docs/architecture.md)
- [数据模型](docs/data-model.md)：字段、口径、质量约束
- [分类体系](docs/schemes.md)：各体系的来源、许可、覆盖、同步与新增办法
- [本站分类目录](docs/taxonomy.md)：设计原则、归类规则、扩展办法、检验记录
- [操作手册](docs/operations.md)：采集、续跑、限流、缓存、页面开发
- [前端说明](docs/frontend.md)：结构、数据加载、常见改动、安全与测试
- [部署](docs/deployment.md)：GitHub Pages、数据更新、发布前检查清单

## 许可证

[MIT](LICENSE)
