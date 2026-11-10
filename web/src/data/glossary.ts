import type { SchemeInfo } from './types';

// 页面上名词与口径的定义。
// 筛选分组的定义跟着分组声明放在 state/query.ts，表格列的定义放在 features/columns.ts，
// 许可证类别的定义在 data/model.ts；这里放其余的，各处和“名词与口径说明”共用，避免说法不一致。

/** 数据超过这么久没更新，顶部就提示。 */
export const STALE_HOURS = 48;

/** 顶部数据时点的含义。 */
export const DATA_TIMES: readonly [label: string, definition: string][] = [
  ['快照日期', '本期总榜快照的日期（UTC）。总榜名次、项目元数据和周 Star 分布都属于这一期。'],
  ['总榜采集', '搜索 Star 最多的项目、确定名次的时间。名次按这一刻的 Star 总数从多到少排列。'],
  ['元数据获取', '各项目的描述、Star、Fork、Issue 等信息的获取时间范围（最早到最晚）。因此表中的 Star 数与总榜采集时刻可能略有出入。'],
  ['周 Star 分布获取', '官方周 Star 分布的获取时间范围。'],
  [`数据已 … 建议重新采集`, `元数据获取至今超过 ${STALE_HOURS} 小时时显示。`],
];

/** 详情里“基本信息”各项的含义。 */
export const FACTS: Record<string, string> = {
  Star: 'Star 总数，是累计规模，不表示近期增长速度。',
  Fork: 'Fork 总数。',
  Watch: '订阅了该仓库动态的用户数（watchers）。',
  贡献者: '向仓库贡献过提交的人数，含匿名贡献者。GitHub 对超大仓库不提供这个数，此时显示 —。',
  提交数: '默认分支上的提交总数。',
  Issue: '未关闭 / 已关闭的 Issue 数，不含 Pull Request。',
  'Pull Request': '未合并且未关闭 / 已合并的 Pull Request 数。',
  发布: 'GitHub Releases 的数量，以及最近一次发布的日期；没有发布时显示“无”。',
  创建: '仓库在 GitHub 上的创建时间，括号内是到数据获取时的年龄。',
  最近推送: '最近一次向仓库推送代码的时间，括号内是距数据获取时的时长。',
  主要语言: 'GitHub 判定的主要语言，即代码字节数最多的语言。',
  许可证: 'GitHub 识别出的许可证标识（SPDX）。NOASSERTION 表示识别到了许可证文件但无法确定类型；未声明表示没有识别出许可证。',
  所有者: '仓库属于组织账号还是个人账号。',
  状态: '是否已归档（作者设为只读、通常不再维护）、是否为 Fork、是否为模板仓库。',
  仓库体积: 'GitHub 统计的仓库占用空间（单位 KB），包含提交历史，不是代码行数。',
};

/** 近期热点的名词。 */
export const TRENDING_TERMS: readonly [label: string, definition: string][] = [
  ['近期热点', '来自 GitHub Trending 页面的每日快照，网页上没有官方接口，GitHub 改版时可能中断。每天更新一次，页面只展示最新一期。'],
  ['今日 / 本周 / 本月新增 Star', 'Trending 页面显示的该时间段新增 Star 数，口径由 GitHub 决定，不能用周 Star 分布复算。'],
  ['榜单条数', '由 GitHub 决定，随时间段和语言变化，不固定为 25 条。'],
  ['总榜第 N 名', '该项目同时也在总 Star 榜里，点击可看站内详情；没有标注的项目不在总榜中，链接到 GitHub。'],
  ['头像', 'Trending 页面上标注的该项目贡献者，可能包含机器人账号；头像来自 github.com，加载失败时不显示。'],
];

/** 范围筛选的含义。 */
export const RANGE_DEFINITIONS = {
  stars: '采集时的 Star 总数范围，含边界；留空表示不限。',
  contributors: '含匿名贡献者。GitHub 对超大仓库不提供这个数，设置范围后这些项目不会出现。',
} as const;

/** 分类筛选的含义（分类树上方显示），随当前体系有无主分类而不同。 */
export function categoryDefinition(primary: boolean): string {
  const how = primary
    ? '每个项目有一个主分类，可有关联分类；“仅主分类”只看主分类，“含关联分类”连关联分类一起看。'
    : '一个项目可以同时属于多个分类。';
  return `当前分类体系里的分类：勾选一个分类即包含它下面的全部子分类。${how}点分类右侧的 ⓘ 查看它的说明（体系有写的话）。`;
}

/** 分类体系的标注方式：名称与含义，页面据此提示可信度。 */
export const METHODS: Record<SchemeInfo['method'], readonly [string, string]> = {
  model: ['语言模型判断', '由语言模型依据项目名称、描述、话题判断，没有经过人工验证，可能有错。'],
  manual: ['研究者人工标注', '研究者逐个项目人工判断并公开了结果。标注发生在数据发布的当时，之后项目可能已经变化。'],
  curated: ['来源方人工策展', '来源方（社区或机构）自己挑选项目放进各分类。收录有取舍：没被收录，不代表项目不属于该类。'],
};

/** 切换分类体系时，对“没被收录的项目”的说明。 */
export const UNCLASSIFIED_NOTE =
  '每个体系只收录一部分项目；没被收录的项目在该体系下没有分类，也不会出现在按分类筛选的结果里。';

/** 分类体系的创建与更新日期的含义，用来判断一个体系的新旧和维护情况。 */
export const SCHEME_TIME_TERMS: [string, string][] = [
  ['创建', '体系诞生的日期：来源仓库的创建日期，或数据集的发布日期；本站分类是首次生成的日期。Wikidata 取它上线的日期。'],
  ['最近更新', '体系内容最近一次变化的日期：来源里相关文件最近一次提交，或数据集最近一次更新；本站分类是最近一次更新。Awesome 清单取各清单仓库里最近一次推送最晚的；每个清单自己的日期在它的分类说明里。'],
  ['取得于', '本站从来源取回数据的日期，不是来源更新的日期。'],
];

/** 超过这么多天没有更新，就提示“较久没有更新”。 */
export const SCHEME_STALE_DAYS = 365;
