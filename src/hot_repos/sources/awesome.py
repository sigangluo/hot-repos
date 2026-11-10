"""来源 awesome：总榜里的 Awesome 类仓库（项目清单）自己的 README。

Awesome 清单是有人围绕一个主题收集的链接，README 里按章节分组——这本身就是一份人工做的分类。
总榜里有大量这样的仓库，所以直接取它们的 README：一个清单是一个一级分类，清单里的章节是二级分类，
清单收录的项目（链接到 GitHub 仓库的条目）属于对应的章节。一个项目可以被多个清单、多个章节收录。

哪些仓库算清单：仓库名含 awesome，或话题含 awesome / awesome-list。README 的位置来自总榜自己的
`default_branch` 与 `readme_path`，不需要额外查询。章节由标题层级自动解析（见 `parse_awesome`），
结构特殊的清单可能不准；总榜里收录不足 `MIN_BOARD_MEMBERS` 个项目的清单不保留。

许可：各清单仓库各自声明许可（多数是 CC0、MIT 或未声明）。本站只保存“清单收录了哪些项目”和章节名称，
不转存清单里的描述文字；各清单的许可写在它的分类说明里。
"""

import json
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import Collected, Fetcher, SourceError
from .explore import first_paragraph, raw_url, repo_name, slugify, unique_label, unique_slug

log = logging.getLogger(__name__)

AWESOME_TOPICS = frozenset({"awesome", "awesome-list", "awesomelist", "awesome-lists"})
INDEX_REPO = "sindresorhus/awesome"  # Awesome 总索引：按领域给清单分组
INDEX_URL = "https://raw.githubusercontent.com/sindresorhus/awesome/main/readme.md"
INDEX_LEVEL = 2  # 总索引里领域分组是二级标题
OTHER_ID = "other"
OTHER_LABEL = "其他（总索引未收录）"
SITE_OTHER_LABEL = "其他（尚未分组）"
GROUPS_FILE = Path(__file__).with_name("awesome_groups.json")  # 本站分组的词表与映射
MIN_BOARD_MEMBERS = 3  # 清单在总榜里至少收录这么多个项目才保留
MIN_LINKS = 5  # README 里至少有这么多个不同的仓库链接才算清单（排除只是名字带 awesome 的普通项目）
MAX_FAILURES = 0.2  # README 取不到的清单超过这个比例时，认为来源出了问题
HEADING_LIMIT = 80

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
FENCE = re.compile(r"^\s*(```|~~~)")
GITHUB_URL = re.compile(r"https?://(?:www\.)?github\.com/[A-Za-z0-9._/-]+", re.I)
# 不属于清单内容的章节：目录、贡献方式、许可、相关清单等。
SKIP_SECTION = re.compile(
    r"^(table of )?contents?$|^toc$|contribut|licen[cs]e|code of conduct|credits?\b|acknowledg"
    r"|^related\b|other awesome|awesome lists?\b|^sponsor|^support|^about\b|footnote|star history"
    r"|^thanks|changelog|translation|back to top|^index$|^awesome\b|目录|目次",
    re.I,
)
# 链接指向的不是项目仓库的第一段路径。
RESERVED_OWNERS = frozenset(
    [
        "topics",
        "orgs",
        "sponsors",
        "features",
        "about",
        "pricing",
        "marketplace",
        "collections",
        "trending",
        "explore",
        "settings",
        "notifications",
        "login",
        "signup",
        "apps",
        "search",
        "readme",
        "security",
        "enterprise",
        "site",
        "contact",
        "customer-stories",
        "issues",
        "pulls",
        "marketplace",
        "new",
    ]
)
# 几乎每个清单开头都有的“Awesome”徽章，不是收录的项目。
BADGE_REPOS = frozenset({"sindresorhus/awesome"})


def is_awesome_list(row: Mapping[str, Any]) -> bool:
    """总榜里的一行是不是 Awesome 清单（且有 README 可取）。"""
    if not row.get("readme_path") or not row.get("default_branch"):
        return False
    name = row["full_name"].split("/")[1].lower()
    return "awesome" in name or any(t.lower() in AWESOME_TOPICS for t in row.get("topics") or [])


def _day(value: Any) -> str | None:
    """日期或时间（datetime 或 ISO 字符串）转成 YYYY-MM-DD；没有值为 None。"""
    return str(value)[:10] if value else None


def clean_heading(text: str) -> str:
    """去掉标题里的链接、HTML、emoji 短码和格式符号，只留文字。"""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # 图片（徽章）整个去掉
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>|:[a-z0-9_+-]+:|[*_`]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—:.")
    return text[:HEADING_LIMIT].rstrip()


def _links(line: str) -> list[str]:
    found = []
    for url in GITHUB_URL.findall(line):
        name = repo_name(url.rstrip("/.").rstrip("."))
        if name and name.split("/")[0].lower() not in RESERVED_OWNERS:
            found.append(name)
    return found


_SKIP = object()  # 标记：当前处在被过滤的章节里


def _attribute(
    lines: list[tuple[int, str | None, str]],
    level_of_sections: int | None,
    own: str,
    skip_title: bool,
) -> dict[str | None, list[str]]:
    """把链接归到“最近的、级别不深于 level_of_sections 的标题”之下。"""
    sections: dict[str | None, list[str]] = {}
    current: Any = None  # None：第一个章节之前
    skip_level: int | None = None  # 正在跳过的章节的标题级别
    first_heading = True
    for level, title, line in lines:
        if level:
            is_title = first_heading and skip_title
            first_heading = False
            if is_title or level_of_sections is None or level > level_of_sections:
                continue
            if skip_level is not None and level > skip_level:
                continue
            skip_level = None
            if not title or SKIP_SECTION.search(title):
                skip_level, current = level, _SKIP
            else:
                current = title
            continue
        if level_of_sections is not None and (current is None or current is _SKIP):
            continue  # 章节之前的简介、徽章，以及被过滤的章节，不算收录
        for name in _links(line):
            if name.lower() == own.lower() or name.lower() in BADGE_REPOS:
                continue
            members = sections.setdefault(None if level_of_sections is None else current, [])
            if name not in members:
                members.append(name)
    return sections


def parse_awesome(text: str, own: str, level: int | None = None) -> dict[str | None, list[str]]:
    """一个清单 README 的 {章节名: [收录的项目 owner/repo]}；没有分章节的清单，键是 None。

    标题层级的判断：只有一个 h1 且排在最前时它是清单标题，不算章节。其余标题里，对每一级试一遍
    “以这一级为章节”，数一数有多少个章节收录了至少 3 个项目；取最浅的、且章节数不少于最大值六成的那一级
    （有的清单把全部内容放在一个“Projects”标题下、再按更深一级分类，直接取最浅一级会丢掉分类）。
    更深的标题并入所在章节；更浅的标题（目录、贡献说明、相关清单等）按名字过滤，被过滤的标题之下的
    内容一并跳过。章节之前的内容（简介、徽章）不算收录。章节与项目都按出现顺序，同一章节里同一项目
    只记一次；清单自己（own）和 Awesome 徽章不算。`level` 给出时直接以这一级标题为章节，不做判断。
    """
    lines: list[tuple[int, str | None, str]] = []  # (标题级别, 标题文字, 正文行)；非标题行级别为 0
    in_code = False
    for raw in re.sub(r"<!--.*?-->", "", text, flags=re.S).splitlines():
        if FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = HEADING.match(raw)
        if m:
            lines.append((len(m[1]), clean_heading(m[2]), raw))
        else:
            lines.append((0, None, raw))
    levels = [lv for lv, _, _ in lines if lv]
    skip_title = levels.count(1) == 1 and levels[:1] == [1]
    if level is not None:
        return _attribute(lines, level, own, skip_title)
    candidates = sorted(set(levels[1:] if skip_title else levels))
    if not candidates:
        return _attribute(lines, None, own, skip_title)
    attributed = {lv: _attribute(lines, lv, own, skip_title) for lv in candidates}
    scores = {lv: sum(len(ms) >= 3 for ms in attributed[lv].values()) for lv in candidates}
    best = max(scores.values())
    if best == 0:  # 没有哪一级能分出像样的章节：当作没分章节
        return _attribute(lines, None, own, skip_title)
    return attributed[min(lv for lv in candidates if scores[lv] >= 0.6 * best)]


def parse_groups(index_text: str) -> dict[str, str]:
    """Awesome 总索引的 {清单仓库名（小写）: 领域分组}：清单出现在多个分组时取第一个。"""
    groups: dict[str, str] = {}
    for group, repos in parse_awesome(index_text, INDEX_REPO, INDEX_LEVEL).items():
        for repo in repos:
            if group is not None:
                groups.setdefault(repo.lower(), group)
    return groups


def _fetch_readmes(fetcher: Fetcher, lists: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """取各清单的 README；个别取不到只记一笔，取不到的太多则报错。"""

    def get(row: Mapping[str, Any]) -> tuple[str, str | None]:
        url = raw_url(row["full_name"], row["default_branch"], row["readme_path"])
        try:
            return row["full_name"], fetcher.text(url)
        except SourceError as e:
            log.warning("awesome：%s", e)
            return row["full_name"], None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(get, lists))
    failed = [name for name, text in results if text is None]
    if len(failed) > MAX_FAILURES * len(lists):
        raise SourceError(f"{len(lists)} 个清单里有 {len(failed)} 个取不到 README")
    return {name: text for name, text in results if text is not None}


@dataclass(frozen=True)
class Group:
    """清单上面的一级分组：编号、名称、说明。"""

    id: str
    label: str
    guidance: str


Assigner = Callable[[str], Group]  # 清单仓库名 -> 它所属的分组


def load_groups() -> dict[str, Any]:
    """本站分组的词表（vocabulary）、清单归属（groups）和不是清单的仓库（exclude）。"""
    return json.loads(GROUPS_FILE.read_text(encoding="utf-8"))


def index_assigner(groups: Mapping[str, str]) -> Assigner:
    """按 Awesome 总索引分组：groups 是 {清单仓库名（小写）: 领域分组名}，没有的归入“其他”。"""

    def assign(name: str) -> Group:
        label = groups.get(name.lower())
        if label is None:
            return Group(
                OTHER_ID,
                OTHER_LABEL,
                f"总榜里的 Awesome 清单中，没有被 Awesome 总索引（{INDEX_REPO}）收录的，所以没有领域分组。",
            )
        return Group(
            slugify(label), label, f"Awesome 总索引（{INDEX_REPO}）里「{label}」章节收录的清单。"
        )

    return assign


def site_assigner(
    vocabulary: Mapping[str, Mapping[str, str]], groups: Mapping[str, str]
) -> Assigner:
    """按本站自己的分组：vocabulary 是 {分组编号: {label, definition}}，groups 是 {清单仓库名: 分组编号}。"""
    by_name = {name.lower(): group for name, group in groups.items()}

    def assign(name: str) -> Group:
        group = by_name.get(name.lower())
        if group not in vocabulary:
            return Group(
                OTHER_ID,
                SITE_OTHER_LABEL,
                "不在本站的分组映射里的清单（多是新进总榜的），尚未分组。",
            )
        item = vocabulary[group]
        return Group(group, item["label"], f"本站定义：{item['definition']}")

    return assign


_SOURCE = {
    "name": "总榜里的 Awesome 类仓库的 README（入口：sindresorhus/awesome）",
    "url": "https://github.com/sindresorhus/awesome",
    "license": "各清单仓库自行声明，见各分类说明",
    "attribution": "各 Awesome 清单的作者与贡献者。本站只保存清单收录了哪些项目及其章节名称，不转存清单的其他内容。",
}
_NOTE_COMMON = (
    "清单由各自的作者围绕一个主题挑选项目，收录有取舍，被收录不等于质量保证；一个项目可以被多个清单、多个章节收录。"
    f"只保留在总榜里收录了至少 {MIN_BOARD_MEMBERS} 个项目的清单。章节名称沿用清单原文，由本站按标题层级自动解析，"
    "个别清单结构特殊时可能不准；各清单的许可见它的分类说明。"
)


def index_meta() -> dict[str, Any]:
    return {
        "name": "Awesome 清单",
        "summary": "总榜里的 Awesome 类仓库（各领域的项目清单）自己的分类：清单按 Awesome 总索引的领域分组，每个清单是一个分类，清单里的章节是子分类，收录的项目属于对应章节。",
        "method": "curated",
        "order": 15,
        "primary": False,
        "note": (
            f"{_NOTE_COMMON}清单的领域分组来自 Awesome 总索引（{INDEX_REPO}），总索引没收录的清单（多是较新的）"
            "归在“其他”组，不是本站另外判断的；想看本站自己的分组，切换到“Awesome 清单 · 本站分组”。"
        ),
        "source": _SOURCE,
    }


def site_meta() -> dict[str, Any]:
    return {
        "name": "Awesome 清单 · 本站分组",
        "summary": "同样是总榜里的 Awesome 清单及其章节，但清单按本站自己的领域词表分组（编程语言、前端、AI 智能体……），与“Awesome 清单”里总索引的分法互为对照。",
        "method": "model",
        "order": 16,
        "primary": False,
        "note": (
            f"{_NOTE_COMMON}清单的分组是本站（语言模型）依据清单名称与描述判断的，词表也是本站定的，没有经过人工验证；"
            "清单与章节来自各 Awesome 仓库。别人（Awesome 总索引）的分法见“Awesome 清单”体系。"
        ),
        "source": _SOURCE,
    }


def _build(
    lists: Sequence[Mapping[str, Any]],
    readmes: Mapping[str, str],
    board: set[str],
    assign: Assigner,
    meta: dict[str, Any],
) -> Collected:
    """三级：领域分组 › 清单 › 章节。分组由 assign 决定；创建与更新日期取各清单仓库的最早创建与最晚推送。"""
    nodes: list[dict[str, Any]] = []
    members: dict[str, list[str]] = {}
    group_ids: set[str] = set()
    list_ids: dict[str, set[str]] = {}  # 分组编号 -> 其下已用的清单编号片段
    created_days: list[str] = []
    updated_days: list[str] = []
    for row in lists:
        name = row["full_name"]
        if name not in readmes:
            continue
        sections = parse_awesome(readmes[name], name)
        distinct = {m for ms in sections.values() for m in ms}
        if (
            len(distinct) < MIN_LINKS
            or len({m for m in distinct if m.lower() in board}) < MIN_BOARD_MEMBERS
        ):
            continue
        group = assign(name)
        if group.id not in group_ids:
            group_ids.add(group.id)
            list_ids[group.id] = set()
            nodes.append(
                {
                    "id": group.id,
                    "label": group.label,
                    "parent": None,
                    "guidance": {"includes": group.guidance},
                }
            )
        list_id = f"{group.id}.{unique_slug(slugify(name), list_ids[group.id])}"
        license_text = f"清单许可：{row['license']}" if row.get("license") else "清单没有声明许可"
        description = first_paragraph(row.get("description") or "", 200)
        created, pushed = _day(row.get("created_at")), _day(row.get("pushed_at"))
        created_days += [created] if created else []
        updated_days += [pushed] if pushed else []
        when = "，".join(
            part
            for part in (
                f"清单仓库创建于 {created}" if created else "",
                f"最近推送 {pushed}" if pushed else "",
            )
            if part
        )
        details = "；".join(part for part in (when, license_text) if part)
        nodes.append(
            {
                "id": list_id,
                "label": name,
                "parent": group.id,
                "guidance": {"includes": f"{description}（{details}）" if description else details},
            }
        )
        used_labels: set[str] = set()
        used_slugs: set[str] = set()
        for section, repos in sections.items():
            if section is None:
                node_id = list_id
            else:
                slug = unique_slug(slugify(section), used_slugs)
                node_id = f"{list_id}.{slug}"
                nodes.append(
                    {
                        "id": node_id,
                        "label": unique_label(section, slug, used_labels),
                        "parent": list_id,
                    }
                )
            for repo in repos:
                members.setdefault(repo, []).append(node_id)
    meta = meta | {"nodes": nodes}
    if created_days:  # 每个清单自己的日期写在它的分类说明里
        meta |= {"created": min(created_days), "updated": max(updated_days or created_days)}
    return Collected(meta=meta, members=members)


def build(
    lists: Sequence[Mapping[str, Any]],
    readmes: Mapping[str, str],
    board: set[str],
    groups: Mapping[str, str] | None = None,
) -> Collected:
    """“Awesome 清单”体系：lists 是总榜里的清单行（按名次），readmes 是 {仓库名: README}，board 是总榜项目名（小写），
    groups 是 {清单仓库名（小写）: 领域分组}，来自 Awesome 总索引，没有的清单归入“其他”组。"""
    return _build(lists, readmes, board, index_assigner(groups or {}), index_meta())


def build_site(
    lists: Sequence[Mapping[str, Any]],
    readmes: Mapping[str, str],
    board: set[str],
    vocabulary: Mapping[str, Mapping[str, str]],
    groups: Mapping[str, str],
) -> Collected:
    """“Awesome 清单 · 本站分组”体系：同样的清单与章节，分组用本站自己的词表与映射。"""
    return _build(lists, readmes, board, site_assigner(vocabulary, groups), site_meta())


def candidate_lists(board_rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """总榜里的 Awesome 清单（按名次），去掉映射文件里声明“不是清单”的仓库。"""
    excluded = {name.lower() for name in load_groups().get("exclude", [])}
    lists = sorted(
        (r for r in board_rows if is_awesome_list(r) and r["full_name"].lower() not in excluded),
        key=lambda r: r["rank"],
    )
    if not lists:
        raise SourceError("总榜里没有找到 Awesome 清单（总榜数据可能不完整）")
    return lists


def _log(label: str, candidates: int, collected: Collected) -> None:
    log.info(
        "%s：%d 个候选清单，保留 %d 个，%d 个节点",
        label,
        candidates,
        sum(n["id"].count(".") == 1 for n in collected.meta["nodes"]),  # 编号只含一个点的是清单
        len(collected.meta["nodes"]),
    )


def collect(fetcher: Fetcher, board_rows: Sequence[Mapping[str, Any]]) -> Collected:
    """board_rows：总榜的项目行（至少含 full_name、rank、default_branch、readme_path、topics、description、license）。"""
    lists = candidate_lists(board_rows)
    readmes = _fetch_readmes(fetcher, lists)
    board = {r["full_name"].lower() for r in board_rows}
    groups = parse_groups(fetcher.text(INDEX_URL))
    if not groups:
        raise SourceError("Awesome 总索引里没有解析出任何领域分组（README 格式可能变了）")
    collected = build(lists, readmes, board, groups)
    if not collected.meta["nodes"]:
        raise SourceError("没有解析出任何 Awesome 清单（README 格式可能变了）")
    _log("awesome", len(lists), collected)
    return collected


def collect_site(fetcher: Fetcher, board_rows: Sequence[Mapping[str, Any]]) -> Collected:
    """同 collect，分组换成本站自己的词表与映射（awesome_groups.json）；README 不会重复下载。"""
    lists = candidate_lists(board_rows)
    readmes = _fetch_readmes(fetcher, lists)
    board = {r["full_name"].lower() for r in board_rows}
    mapping = load_groups()
    collected = build_site(lists, readmes, board, mapping["vocabulary"], mapping["groups"])
    if not collected.meta["nodes"]:
        raise SourceError("没有解析出任何 Awesome 清单（README 格式可能变了）")
    _log("awesome-site", len(lists), collected)
    return collected
