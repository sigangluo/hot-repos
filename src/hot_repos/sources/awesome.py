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

import logging
import re
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import Collected, Fetcher, SourceError
from .explore import first_paragraph, raw_url, repo_name, slugify, unique_label, unique_slug

log = logging.getLogger(__name__)

AWESOME_TOPICS = frozenset({"awesome", "awesome-list", "awesomelist", "awesome-lists"})
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


def parse_awesome(text: str, own: str) -> dict[str | None, list[str]]:
    """一个清单 README 的 {章节名: [收录的项目 owner/repo]}；没有分章节的清单，键是 None。

    标题层级的判断：只有一个 h1 且排在最前时它是清单标题，不算章节。其余标题里，对每一级试一遍
    “以这一级为章节”，数一数有多少个章节收录了至少 3 个项目；取最浅的、且章节数不少于最大值六成的那一级
    （有的清单把全部内容放在一个“Projects”标题下、再按更深一级分类，直接取最浅一级会丢掉分类）。
    更深的标题并入所在章节；更浅的标题（目录、贡献说明、相关清单等）按名字过滤，被过滤的标题之下的
    内容一并跳过。章节之前的内容（简介、徽章）不算收录。章节与项目都按出现顺序，同一章节里同一项目
    只记一次；清单自己（own）和 Awesome 徽章不算。
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
    candidates = sorted(set(levels[1:] if skip_title else levels))
    if not candidates:
        return _attribute(lines, None, own, skip_title)
    attributed = {lv: _attribute(lines, lv, own, skip_title) for lv in candidates}
    scores = {lv: sum(len(ms) >= 3 for ms in attributed[lv].values()) for lv in candidates}
    best = max(scores.values())
    if best == 0:  # 没有哪一级能分出像样的章节：当作没分章节
        return _attribute(lines, None, own, skip_title)
    return attributed[min(lv for lv in candidates if scores[lv] >= 0.6 * best)]


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


def build(
    lists: Sequence[Mapping[str, Any]], readmes: Mapping[str, str], board: set[str]
) -> Collected:
    """lists：总榜里的清单行（按名次）；readmes：{仓库名: README 文本}；board：总榜项目名（忽略大小写的小写形式）。"""
    nodes: list[dict[str, Any]] = []
    members: dict[str, list[str]] = {}
    used_ids: set[str] = set()
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
        list_id = unique_slug(slugify(name), used_ids)
        license_text = f"清单许可：{row['license']}" if row.get("license") else "清单没有声明许可"
        description = first_paragraph(row.get("description") or "", 200)
        nodes.append(
            {
                "id": list_id,
                "label": name,
                "parent": None,
                "guidance": {
                    "includes": f"{description}（{license_text}）" if description else license_text
                },
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
    meta = {
        "name": "Awesome 清单",
        "summary": "总榜里的 Awesome 类仓库（各领域的项目清单）自己的分类：每个清单是一个分类，清单里的章节是子分类，收录的项目属于对应章节。",
        "method": "curated",
        "order": 15,
        "primary": False,
        "note": (
            "清单由各自的作者围绕一个主题挑选项目，收录有取舍，被收录不等于质量保证；一个项目可以被多个清单、多个章节收录。"
            f"只保留在总榜里收录了至少 {MIN_BOARD_MEMBERS} 个项目的清单。章节名称沿用清单原文，由本站按标题层级自动解析，"
            "个别清单结构特殊时可能不准；各清单的许可见它的分类说明。"
        ),
        "source": {
            "name": "总榜里的 Awesome 类仓库的 README（入口：sindresorhus/awesome）",
            "url": "https://github.com/sindresorhus/awesome",
            "license": "各清单仓库自行声明，见各分类说明",
            "attribution": "各 Awesome 清单的作者与贡献者。本站只保存清单收录了哪些项目及其章节名称，不转存清单的其他内容。",
        },
        "nodes": nodes,
    }
    return Collected(meta=meta, members=members)


def collect(fetcher: Fetcher, board_rows: Sequence[Mapping[str, Any]]) -> Collected:
    """board_rows：总榜的项目行（至少含 full_name、rank、default_branch、readme_path、topics、description、license）。"""
    lists = sorted((r for r in board_rows if is_awesome_list(r)), key=lambda r: r["rank"])
    if not lists:
        raise SourceError("总榜里没有找到 Awesome 清单（总榜数据可能不完整）")
    readmes = _fetch_readmes(fetcher, lists)
    board = {r["full_name"].lower() for r in board_rows}
    collected = build(lists, readmes, board)
    if not collected.meta["nodes"]:
        raise SourceError("没有解析出任何 Awesome 清单（README 格式可能变了）")
    log.info(
        "awesome：%d 个候选清单，保留 %d 个，%d 个节点",
        len(lists),
        sum(n.get("parent") is None for n in collected.meta["nodes"]),
        len(collected.meta["nodes"]),
    )
    return collected
