# 数据模型

`data/` 是项目的规范数据，由采集命令生成，提交到 git。表结构的唯一定义在 [`src/hot_repos/schema.py`](../src/hot_repos/schema.py)，本文的字段表由测试对照该文件，字段增减时两处必须同步。

| 文件 | 内容 | 粒度 |
|---|---|---|
| `repos.parquet` | 当前快照的项目元数据 | 一行一个项目 |
| `star_weeks.parquet` | 官方周 Star 分布 | 一行一个项目的一周 |
| `rank_history.parquet` | 历次快照的总榜名次 | 一行一个快照日期的一个名次 |
| `manifest.json` | 快照日期、运行参数、改名与缺失记录 | 单个对象 |
| `trending/YYYY-MM-DD.parquet` | GitHub Trending 榜单的每日快照 | 一行一个（日期，时间段，语言）榜单中的一个项目 |
| `schemes/<编号>/scheme.json` | 一个分类体系的定义：名称、来源、节点（可以先于标注存在） | 单个对象 |
| `schemes/<编号>/labels.parquet` | 该体系对项目的标注（可选） | 一行一个被标注的项目 |

通用约定：

- 时间列为带时区（UTC）的微秒级时间戳；日期列为不带时区的日期。
- 缺失值一律为 NULL。不用 0、空字符串或占位值代替；不插值、不补零。
- 列表列（话题、语言、赞助链接）没有内容时为空列表，不为 NULL。
- `full_name` 是项目的当前名称（`owner/repo`）。比较时忽略大小写，保存时保留 GitHub 返回的大小写。
- 仓库改名后使用当前名称，采集时用过的其他名称记录在 `manifest.json` 的 `aliases`。

## 数据文件

### repos.parquet

排序：按 `rank` 升序。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `full_name` | 字符串 | 否 | 项目当前名称，主键 |
| `rank` | 整数 | 否 | 总榜名次，按采集时 Star 数降序；无法获取的仓库在名次上留空档，因此不一定连续 |
| `description` | 字符串 | 是 | 仓库描述 |
| `homepage` | 字符串 | 是 | 仓库填写的主页地址 |
| `owner_type` | 字符串 | 否 | 所有者类型，`Organization` 或 `User` |
| `created_at` | 时间 | 否 | 创建时间 |
| `pushed_at` | 时间 | 是 | 最近一次推送时间 |
| `updated_at` | 时间 | 否 | 仓库信息最近更新时间（含非代码变更） |
| `is_archived` | 布尔 | 否 | 是否已归档 |
| `is_fork` | 布尔 | 否 | 是否为 fork |
| `is_template` | 布尔 | 否 | 是否为模板仓库 |
| `disk_usage_kb` | 整数 | 是 | 仓库占用空间，单位 KB；GitHub 未返回时为 NULL |
| `stars` | 整数 | 否 | 元数据获取时的 Star 总数 |
| `forks` | 整数 | 否 | Fork 数 |
| `watchers` | 整数 | 否 | Watcher 数 |
| `open_issues` | 整数 | 否 | 未关闭 Issue 数 |
| `closed_issues` | 整数 | 否 | 已关闭 Issue 数 |
| `open_prs` | 整数 | 否 | 未合并且未关闭的 PR 数 |
| `merged_prs` | 整数 | 否 | 已合并 PR 数 |
| `discussions_enabled` | 布尔 | 否 | 是否启用讨论区 |
| `discussions` | 整数 | 否 | 讨论数；未启用讨论区时为 0 |
| `primary_language` | 字符串 | 是 | GitHub 判定的主要语言 |
| `languages` | 列表<结构体> | 否 | 代码字节数前 10 的语言，元素为 `name`（语言名）和 `bytes`（字节数），按字节数降序 |
| `topics` | 列表<字符串> | 否 | 话题，最多 30 个 |
| `license` | 字符串 | 是 | 许可证 SPDX 标识；`NOASSERTION` 表示 GitHub 识别到许可证文件但无法确定类型；NULL 表示未声明 |
| `default_branch` | 字符串 | 是 | 默认分支名；空仓库为 NULL |
| `commit_count` | 整数 | 是 | 默认分支的提交数；空仓库为 NULL |
| `contributors` | 整数 | 是 | 贡献者数（含匿名）；GitHub 对超大仓库不提供，此时为 NULL |
| `release_count` | 整数 | 否 | 发布数 |
| `latest_release_tag` | 字符串 | 是 | 最新发布的标签；无发布为 NULL |
| `latest_release_at` | 时间 | 是 | 最新发布的时间；与 `latest_release_tag` 同时有值或同时为 NULL |
| `funding` | 列表<结构体> | 否 | 赞助链接，元素为 `platform` 和 `url` |
| `readme_path` | 字符串 | 是 | README 在仓库根目录的文件名，依次尝试 `README.md`、`readme.md`、`Readme.md`、`README.markdown`；没有 Markdown 版本为 NULL。正文不保存，需要时读取 `raw.githubusercontent.com/{full_name}/HEAD/{readme_path}` |
| `fetched_at` | 时间 | 否 | 本行元数据的获取时间 |
| `star_weeks_fetched_at` | 时间 | 是 | 该项目周 Star 分布的获取时间；未获取为 NULL |
| `star_weeks_pages_fetched` | 整数 | 是 | 已抓取的周分布页数 |
| `star_weeks_pages_total` | 整数 | 是 | 该项目周分布的总页数；已抓页数小于总页数表示只有近期部分 |

`star_weeks_*` 三列同时有值或同时为 NULL。

### star_weeks.parquet

排序：按 `full_name`、`week_start` 升序。主键 `(full_name, week_start)`。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `full_name` | 字符串 | 否 | 项目名称，必须存在于 `repos.parquet` |
| `week_start` | 日期 | 否 | 该周的起始日，GitHub 以周日为周起点，采集时校验 |
| `stars` | 整数 | 否 | 该周内新增且至今仍保留的 Star 数 |
| `days` | 列表<整数> | 否 | 周日到周六各日的 Star 数，长度 7，之和等于 `stars` |

### rank_history.parquet

排序：按 `snapshot_date`、`rank` 升序。主键 `(snapshot_date, rank)`。同一天重复运行时，替换当天的快照。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `snapshot_date` | 日期 | 否 | 快照日期（UTC） |
| `rank` | 整数 | 否 | 当日总榜名次 |
| `full_name` | 字符串 | 否 | 采集该快照时解析出的项目名称；历史快照中的名称可能与当前名称不同 |
| `stars` | 整数 | 否 | 排名时的 Star 数 |
| `captured_at` | 时间 | 否 | 排名的采集时间，同一快照内相同 |

最新快照必须与 `repos.parquet` 的 `rank`、`full_name` 完全对应。

### manifest.json

| 字段 | 类型 | 含义 |
|---|---|---|
| `schema_version` | 整数 | 数据契约版本，与 `config.SCHEMA_VERSION` 一致 |
| `snapshot_date` | 字符串 | 当前快照日期（UTC，`YYYY-MM-DD`），等于 `rank_history` 的最新快照 |
| `board_size` | 整数 | 目标榜单名额；实际项目数可能更少 |
| `rank_captured_at` | 字符串 | 总榜的采集时间（ISO 8601，带时区） |
| `run_at` | 字符串 | 本次运行的开始时间（ISO 8601，带时区） |
| `star_weeks_per_page` | 整数 | 周分布接口每页的周数 |
| `aliases` | 对象 | 键为当前名称，值为采集中出现过的全部名称（含当前名称） |
| `missing` | 列表<字符串> | 榜单中出现、但已删除或下架而无法获取的仓库 |

### trending/YYYY-MM-DD.parquet

位于 `data/trending/`，每天一个文件，只追加：新的一天新增一个文件，同一天重复运行时替换当天的文件，不改动更早的文件。它独立于上面的总榜数据：不进入 `manifest.json`，上榜项目也不要求出现在 `repos.parquet`（大多数不在其中）。

写入顺序：先“全部语言”，再按 `config.TRENDING_LANGUAGES` 的顺序；每个语言内依次为 `daily`、`weekly`、`monthly`，榜单内按 `rank`。读取时不要依赖行序，按主键 `(snapshot_date, since, language, rank)` 取用。

| 字段 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `snapshot_date` | 日期 | 否 | 快照日期（UTC），等于文件名 |
| `since` | 字符串 | 否 | 时间段：`daily`、`weekly`、`monthly` |
| `language` | 字符串 | 否 | 榜单的语言筛选：`all` 表示全部语言，其余为 Trending 地址中的写法（小写，如 `c++`），取值见 `config.TRENDING_LANGUAGES` |
| `rank` | 整数 | 否 | 榜单中的位置，按页面顺序，从 1 开始 |
| `full_name` | 字符串 | 否 | 项目名称（`owner/repo`），保留页面上的大小写 |
| `description` | 字符串 | 是 | 页面上的简介，没有则为 NULL |
| `repo_language` | 字符串 | 是 | 页面上的主要语言，没有则为 NULL |
| `stars` | 整数 | 否 | 抓取时的 Star 总数 |
| `forks` | 整数 | 否 | 抓取时的 Fork 总数 |
| `period_stars` | 整数 | 否 | 页面显示的该时间段新增 Star（今日、本周或本月） |
| `built_by` | 列表<字符串> | 否 | 页面上 Built by 的头像对应的用户名，机器人账号也在内；没有则为空列表 |
| `captured_at` | 时间 | 否 | 抓取时间，同一快照内相同 |

### schemes/<编号>/scheme.json

一个分类体系的定义。体系回答“这些项目分别属于什么类”：来源是别人已经做好的公开分类（Borges 等的人工标注、CNCF Landscape 等），只保存“总榜里的哪个项目属于来源里的哪个类”，不重新标注，并注明出处与许可。体系可以先于标注存在（定义好、标注还没有时，页面不列出它）；有标注就必须有定义。编号只能含小写字母、数字和连字符。各体系的来源、口径与同步办法见 [schemes.md](schemes.md)。

| 字段 | 类型 | 含义 |
|---|---|---|
| `name` | 字符串 | 体系的显示名 |
| `summary` | 字符串 | 一句话说明这个体系是什么、谁做的、怎么做的 |
| `method` | 字符串 | 标注方式：`model`（语言模型判断，未经人工验证）、`manual`（研究者人工标注）、`curated`（来源方人工策展）。页面据此提示可信度 |
| `order` | 整数 | 可选。页面列出体系的顺序，小的在前，默认 100；同值按编号 |
| `primary` | 布尔 | 每个被标注的项目是否都有一个主分类。`false` 表示体系里一个项目只有若干并列的分类（如各种合集） |
| `source` | 对象 | 外部来源的出处：`name`、`url`（http 开头）、`license`（SPDX 标识）、可选的 `attribution`（署名） |
| `created` | 字符串 | 体系的创建日期（`YYYY-MM-DD`）：来源仓库的创建日期，或数据集的发布日期。必填，页面据此判断体系的新旧 |
| `updated` | 字符串 | 体系内容最近一次变化的日期（`YYYY-MM-DD`）：来源里相关文件最近一次提交，或数据集最近一次更新。必填，不早于 `created`，页面据此判断体系有没有在维护 |
| `as_of` | 字符串 | 取得来源数据的日期（`YYYY-MM-DD`），不是来源更新的日期；有 `source` 的体系必须有，没有 `source` 的不应有 |
| `note` | 字符串 | 可选。使用时需要知道的说明，如数据的年代、可信度、覆盖范围，页面在“关于这个体系”里原样展示；没有说明时省略该字段 |
| `nodes` | 列表<对象> | 体系的节点（分类），按“父节点在前、子节点在后”的顺序排列 |

节点的字段：`id`（编号，全体系唯一）、`label`（名称，同一父节点下不重复；外部体系沿用来源的原文）、`parent`（父节点编号，一级节点没有此字段）、可选的 `guidance`（`includes` / `excludes`，说明该分类收什么、不收什么，来源没有说明的就不写；每个分类自己有来源日期的体系，如 Awesome 清单，把日期写在这里）。编号用「.」连接各级，子节点编号以父节点编号加「.」开头，如 `dev.ai-coding.skills`，一级节点编号不含「.」。编号一旦发布就保持稳定，改名只改 `label`。

### schemes/<编号>/labels.parquet

排序：按 `full_name` 忽略大小写升序。主键 `full_name`。只包含被标注的项目，没被标注的项目没有行。

| 字段 | 类型 | 含义 |
|---|---|---|
| `full_name` | 字符串 | 项目名称，必须与 `repos.parquet` 完全一致（含大小写） |
| `category` | 字符串 | 主分类：体系节点编号，取该项目最具体的一级；体系的 `primary` 为 `false` 时为 NULL，否则必须有值 |
| `related` | 列表<字符串> | 其余分类：项目同时属于的其他节点编号，没有则为空列表；不含主分类。`primary` 为 `false` 的体系，项目的全部分类都放在这里，且不能为空 |

## 口径

- **Star 总数是累计规模**，不表示近期增长速度。
- **排名与元数据的时点不同**。名次和 `rank_history.stars` 取自榜单采集时刻，`repos.stars` 取自元数据获取时刻，两者可能略有差异。各时点见 `rank_captured_at` 与 `fetched_at`。
- **周 Star 分布**是 GitHub 官方统计：采集时仍保留的 Star 按创建时间的分布。已取消或被清理的 Star 不在其中，因此不能据此还原历史净 Star 数或净增长。缺失的周不推算。
- **周边界由 GitHub 定义**：每周从周日开始，按周存放的 `days` 保留逐日计数。当前数据的周起点都在 UTC 周日零点，采集时对此校验，不符合则报错而不是静默转换。
- **总榜搜索是一次采集快照**：搜索结果持续变化，榜单不是事务一致的时点排名。
- **Trending 来自网页，不是接口**：数据靠解析 `github.com/trending` 页面得到，GitHub 改版时会失效，解析器对结构变化报错而不是猜测。
- **Trending 的榜单长度不固定**：页面实际条数随时间段、语言变化（观察到 3 到 22 条），不总是 25；某个语言当天没有上榜项目时，该语言当天没有行，这与页面所示一致。
- **`period_stars` 的口径由 GitHub 决定**：是页面显示的数字，不能用 `star_weeks` 复算，也不保证与之相符。
- **分类的可信度由数据自己说明**：体系可以来自任何来源，仓库不假定它经过人工验证，也不保证覆盖全部项目；标注方式（`method`）、来源与许可（`source`）、覆盖范围和已知问题（`note`）都写在 `scheme.json` 里，页面原样展示。
- **每个体系只收录一部分项目**：外部体系只覆盖来源里收录、且今天仍在总榜里的项目，没被收录不代表项目不属于那一类；各体系之间的分类互相独立，不做映射。
- **分类可以重叠**：有主分类的体系里主分类只有一个，关联分类可以有多个；页面按主分类和关联分类一起统计，所以各分类的项目数之和可能大于已分类的项目数。
- **分类与总榜按项目名对齐**：`fetch` 时，改名的项目按 `manifest.json` 的 `aliases` 换成当前名称，已不在总榜里的项目其标注被丢弃（日志里会列出）；新进总榜的项目没有分类，外部体系要重新同步（`schemes sync`）才会补上。
- **上游数据的已知不一致原样保留**：例如个别仓库 `release_count` 为 0 却有最新发布，这是 GitHub 返回的结果，不做修正。

## 完整性约束

由 `hot_repos.validate` 检查，可用于 CI：

- 各文件存在，表结构与 `schema.py` 一致；`manifest.json` 字段齐全、类型正确、版本匹配。
- `repos`：`full_name` 唯一（忽略大小写）且为 `owner/repo` 形式；`rank` 唯一且从 1 起；计数非负；`updated_at` 不早于 `created_at`；话题无重复；`readme_path` 属于已知文件名；`star_weeks_*` 三列一致。
- `rank_history`：每个快照内名次唯一、名称唯一，名次与 Star 数降序对应，`captured_at` 一致。
- `star_weeks`：主键唯一，周起点为周日，同一项目的周连续（间隔 7 天），`days` 长度 7 且之和等于 `stars`，项目存在于 `repos`；有周数据的项目 `star_weeks_*` 必须有值，周数不超过已抓页数能容纳的上限。
- 跨文件：`manifest.snapshot_date` 等于最新快照；最新快照与 `repos` 的名次和名称一一对应；`board_size` 不小于项目数；`aliases` 的键存在于 `repos` 且包含当前名称；`missing` 与 `repos` 不重叠。
- `schemes/`（每个体系）：有标注就必须有定义，只有定义是允许的；体系编号合法；`name`、`summary` 非空，`method` 是已知取值，`primary` 是布尔值，`created`、`updated` 是日期且 `created` 不晚于 `updated`，有 `source` 的体系来源信息完整且有 `as_of`；`nodes` 齐全，节点编号唯一、父节点存在且排在前面、编号以父节点编号开头、同一父节点下名称不重复；标注的表结构与 `schema.py` 一致，`full_name` 唯一且与 `repos.parquet` 完全一致，`category`、`related` 的编号都在体系中，有主分类的体系每行都有 `category`、没有主分类的体系 `category` 为 NULL 且 `related` 不为空，`related` 无重复、不含 `category`。
- `trending`：文件名是合法日期且等于 `snapshot_date`；`captured_at` 一致且其日期（UTC）等于文件名；每个（时间段，语言）榜单内 `rank` 从 1 起连续、`full_name` 唯一；"全部语言"三个时间段齐全；计数非负。写入前先按同样规则检查，不通过则不写入。

## 示例查询（DuckDB）

```python
import duckdb

duckdb.sql("""
  select rank, full_name, stars from 'data/repos.parquet' order by rank limit 10
""").show()

duckdb.sql("""
  select week_start, stars, sum(stars) over (order by week_start) as cumulative
  from 'data/star_weeks.parquet'
  where full_name = 'n8n-io/n8n' order by week_start
""").show()
```
