# 操作手册

## 环境

- Python 3.12+，用 [uv](https://docs.astral.sh/uv/) 管理：`uv sync`
- GitHub Token：依次读取环境变量 `GITHUB_TOKEN`、`GH_TOKEN`，再尝试 `gh auth token`。只在内存中使用，只请求公开数据。

## 采集

```bash
uv run hot-repos fetch --top 5000
```

| 参数 | 含义 |
|---|---|
| `-n`, `--top` | 总榜名额（必填） |
| `--max-age-hours` | 缓存有效时长，默认 24 小时；超过则重新抓取 |
| `--refresh` | 忽略缓存，全部重新抓取 |
| `--star-weeks` | `recent` 只取最近一页（默认，约 30 周）；`full` 向创建时间回溯取全部页；`skip` 沿用 `data/` 中已有的周分布 |
| `--rps` | 每秒请求数上限，默认 12 |
| `--data-dir`, `--cache-dir` | 数据与缓存目录，默认 `data/` 与 `.cache/` |

流程分四步：总榜搜索 → 仓库元数据（GraphQL）→ 贡献者数 → 周 Star 分布。结果先写入 `.cache/staging/`，通过校验后才替换 `data/`；未通过时 `data/` 保持原样并报错。

## Trending

```bash
uv run hot-repos trending
```

不需要 Token，也不会发送 Token：Trending 只有网页，没有接口，由 `github/trending.py` 解析页面。每次抓取"全部语言"加 `config.TRENDING_LANGUAGES` 中的各语言，每个语言三个时间段，共 33 个请求，默认每秒 1 个，约 2 分钟。结果写入 `data/trending/<UTC 日期>.parquet`，同一天重跑会替换当天的文件。

| 参数 | 含义 |
|---|---|
| `--rps` | 每秒请求数上限，默认 1 |
| `--data-dir` | 数据目录，默认 `data/`；快照写入其下的 `trending/` |

快照要么完整要么不写：任何一页失败、页面不是 Trending 页、字段缺失、"新增 Star"的时间词与所请求的时间段不符、"全部语言"的某个时间段少于 5 条，都会报错退出，不产生当天的文件，已有的文件不受影响。出现这类错误通常说明页面结构变了，需要更新 `github/trending.py`，并用新页面更新 `tests/data/` 下的样本。

每天约增加 50 KB（一年约 18 MB）。每日定时任务见 [deployment.md](deployment.md)。

## 分类体系

分类体系是可选数据，每个体系一个目录 `data/schemes/<编号>/`（`scheme.json` 定义，`labels.parquet` 标注），字段与口径见 [data-model.md](data-model.md)，各体系的来源、许可和接入办法见 [schemes.md](schemes.md)，本站分类目录的设计见 [taxonomy.md](taxonomy.md)。

```bash
uv run hot-repos schemes sync            # 同步全部外部体系
uv run hot-repos schemes sync borges cncf  # 只同步指定的
```

`schemes sync` 从各公开来源取别人已经做好的分类，把今天总榜里的项目对上去，写入 `data/schemes/<编号>/`；只保存“哪个项目属于来源里的哪个类”，不重新标注。某个来源取不到或格式变了，只有它失败（该体系已有数据保持原样），命令以非零状态退出。GitHub 接口用 `GITHUB_TOKEN` / `gh auth token`（没有也能跑，但额度只有每小时 60 次）。**总榜更新（`fetch`）后建议同步一次**：新进总榜的项目才会出现在外部体系里。

- **本站分类（`site`）**：由语言模型判断，目前覆盖总榜中创建不足一年的 361 个项目，未经人工验证。仓库里没有生成它的命令，更新 `labels.parquet` 用 `hot_repos.schemes` 的 `write_meta` / `write_rows`（按 schema 校验、行按项目名排序），之后运行 `validate`。节点编号必须稳定，新增分类先改 `scheme.json`。
- **`fetch` 会维护对齐**：对每个体系，改名的项目换成当前名称，已不在总榜里的项目其标注被丢弃，日志里列出改名数；这些标注和总榜一起先写入暂存目录、校验通过后才发布。
- **移除某个体系**：删除它的目录即可，导出时会一并清除旧的 `scheme-<编号>.json`。

## 断点续跑与限流

- 每一步每完成一批就写入缓存。中断（网络、限流、手动停止）后，**重跑相同命令**即可，只补缺口，通常不需要 `--refresh`。
- 所有请求（含重试）合计不超过 `--rps`；搜索接口另有每次至少间隔 2.1 秒的限制。
- 触发 GitHub 限流时，所有请求一起等待到额度恢复；网络错误和 5xx 退避重试，重试用尽后报错退出，进度保留。
- 仓库已删除或下架时，记入 `manifest.json` 的 `missing`，其名次留空档。临时性错误不会被当作"已删除"。

## 已知限制

- **`--star-weeks recent` 会替换已有的更长历史**：`data/` 是一份快照，每次运行整体重写。之前用 `full` 抓过的历史，在用 `recent` 重跑后会被近期一页取代（运行时会给出警告）。要保留请用 `--star-weeks full` 或 `skip`。
- **发布 `data/` 几乎原子，但不是绝对原子**：先把全部文件复制成临时文件（失败时 `data/` 不变），再依次重命名。重命名这几步被强杀的话可能留下新旧混合的状态，`validate` 能发现，重跑即可修复。
- **Trending 的历史只能从开始采集那天算起**：页面不保留过去的榜单，无法补抓。
- **Trending 的数据靠解析网页**：GitHub 改版会使采集失败（报错，不写入），需要手工修复解析器。使用前请自行确认 GitHub 的服务条款允许这种访问。
- **首次完整采集受限流支配**：REST 每小时 5000 次，而贡献者数和周分布第一页合计约需 10000 次，中途会等待额度重置。

## 缓存目录 `.cache/`

可随时整体删除，下次运行会重新抓取。

| 文件 | 内容 |
|---|---|
| `search_<n>.json` | 总榜搜索结果 |
| `search_<n>_progress.json` | 搜索进行中的断点，完成后删除 |
| `graphql_<哈希>.jsonl` | 仓库元数据；哈希由查询字段决定，字段变化后旧缓存自动作废并清理 |
| `contributors.jsonl` | 贡献者数 |
| `star_weeks.jsonl` | 周 Star 分布，按页缓存 |
| `staging/` | 发布前的暂存数据 |

`.jsonl` 缓存在每次成功运行结束时压缩：只保留每个键的最新记录，并清除超过 30 天的记录。

## 校验

```bash
uv run hot-repos validate
```

同时检查总榜数据、各分类体系和 `data/trending/` 下的全部快照，检查项见 [data-model.md](data-model.md#完整性约束)。提交 `data/` 前必须通过；测试中也包含对已提交数据的校验。

## 导出页面数据

```bash
uv run hot-repos export
```

先校验 `data/`，通过后在 `web/public/data/` 生成 `meta.json`、`repos.json`、`details.json`、`weeks.json`，有 Trending 快照时再生成 `trending.json`（最新一天），有分类体系时每个体系再生成一个 `scheme-<编号>.json`。这些是生成物，不提交；本地开发和 Pages 构建时重新生成。文件内容见 [architecture.md](architecture.md) 的第 7 条设计决定与 `export_web.py` 的模块说明。

## 页面开发与构建

需要 Node.js 22+。先导出页面数据，再启动开发服务器：

```bash
uv run hot-repos export
cd web
npm ci
npm run dev          # 开发，热更新
npm run build        # 类型检查并构建到 web/dist
npm run preview      # 预览构建结果
npm test             # 前端单元测试
```

页面通过 HTTP 访问，不能双击 `index.html` 以 `file://` 打开。README 正文在查看详情时从 `raw.githubusercontent.com` 读取，需要联网。

首屏只加载约 12KB（gzip）的脚本和 `repos.json`；ECharts、marked、DOMPurify 在首次打开详情或 README 时才加载。

## 开发

```bash
uv run pytest          # 测试，不访问真实 GitHub
uv run ruff check .    # 代码检查
uv run ruff format .   # 格式化
```
