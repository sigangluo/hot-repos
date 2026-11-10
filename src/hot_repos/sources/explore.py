"""来源 explore：GitHub 官方 Explore 的主题合集（github/explore 仓库的 collections/）。

每个合集是 `collections/<slug>/index.md`：YAML 头里有 `items`（项目列表）、`display_name`，
正文是合集的介绍。一个项目可以属于多个合集，所以体系没有主分类（`primary` 为 False）。
内容以 CC-BY-4.0 发布（仓库 LICENSE.txt 与 notices.md），署名文字用 notices.md 建议的写法。

本模块同时放着几个来源共用的小工具：项目名规整（`repo_name`）、节点编号（`slugify`、`unique_slug`）、
列出 GitHub 仓库里的文件（`list_files`）、YAML 加载（`load_yaml`）。
"""

import logging
import re
from typing import Any
from urllib.parse import quote, urlparse

import yaml

from . import Collected, Fetcher, SourceError

log = logging.getLogger(__name__)

REPO = "github/explore"
BRANCH = "main"
COLLECTION_PATH = re.compile(r"collections/[^/]+/index\.md")
FRONT_MATTER = re.compile(r"\A\ufeff?---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)", re.DOTALL)
DESCRIPTION_LIMIT = 300

_OWNER = re.compile(r"[A-Za-z0-9-]+")
_REPO = re.compile(r"[A-Za-z0-9_.-]+")
_GITHUB_HOSTS = ("github.com", "www.github.com")

# 优先用 C 版加载器（landscape.yml 有 1 MB 多），没有则退回纯 Python 版
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def load_yaml(text: str) -> Any:
    """解析 YAML，格式错误统一抛 `yaml.YAMLError`。"""
    return yaml.load(text, Loader=_YAML_LOADER)  # noqa: S506  只用 SafeLoader 系列


def repo_name(value: object) -> str | None:
    """把来源里各种写法的项目引用规整为 `owner/repo`；不是 GitHub 仓库（组织主页、视频、其他站点）返回 None。

    接受 `owner/repo`（可带结尾斜杠）、`https://github.com/owner/repo[.git][/子路径]`。
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if "://" in text:
        parsed = urlparse(text)
        if (parsed.hostname or "").lower() not in _GITHUB_HOSTS:
            return None
        path = parsed.path
    else:
        path = re.split(r"[?#]", text, maxsplit=1)[0]
        if path.lower().startswith(tuple(f"{h}/" for h in _GITHUB_HOSTS)):
            path = path.split("/", 1)[1]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if not _OWNER.fullmatch(owner) or not _REPO.fullmatch(repo) or repo in (".", ".."):
        return None
    return f"{owner}/{repo}"


def slugify(text: str) -> str:
    """小写字母、数字和连字符组成的节点编号片段；没有可用字符时返回 "x"。"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "x"


def unique_slug(slug: str, used: set[str]) -> str:
    """片段重复时加数字后缀（-2、-3……），并登记到 used。"""
    candidate, n = slug, 2
    while candidate in used:
        candidate = f"{slug}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def unique_label(label: str, hint: str, used: set[str]) -> str:
    """同一父节点下名称不能重复：重复时附上 hint（通常是编号片段）区分，并登记到 used。"""
    candidate = label if label not in used else f"{label} ({hint})"
    used.add(candidate)
    return candidate


def raw_url(repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{quote(path)}"


def list_files(fetcher: Fetcher, repo: str, branch: str, pattern: re.Pattern[str]) -> list[str]:
    """用 Git Trees 接口列出仓库里路径匹配 pattern 的文件（排序后返回）。"""
    tree = fetcher.json(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
        raise SourceError(f"{repo} 的文件列表格式不对（GitHub 接口可能变了）")
    if tree.get("truncated"):
        raise SourceError(f"{repo} 的文件列表被 GitHub 截断，无法完整列出")
    paths = sorted(
        item["path"]
        for item in tree["tree"]
        if item.get("type") == "blob" and pattern.fullmatch(item.get("path", ""))
    )
    if not paths:
        raise SourceError(f"{repo} 里没有找到匹配 {pattern.pattern} 的文件（目录结构可能变了）")
    return paths


def first_paragraph(body: str, limit: int = DESCRIPTION_LIMIT) -> str | None:
    """正文的第一段（空白折叠成单个空格），超过 limit 个字符时在词边界截断并加「…」。"""
    for block in re.split(r"\n\s*\n", body.strip()):
        text = re.sub(r"\s+", " ", block).strip()
        if re.search(r"[A-Za-z0-9\u4e00-\u9fff]", text):
            if len(text) > limit:
                text = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:，。；：") + "…"
            return text
    return None


def parse_collection(text: str) -> tuple[dict[str, Any], str] | None:
    """拆出一个合集文件的（YAML 头，正文）；没有头或格式不对返回 None。"""
    m = FRONT_MATTER.match(text)
    if not m:
        return None
    try:
        head = load_yaml(m[1])
    except yaml.YAMLError:
        return None
    return (head, m[2]) if isinstance(head, dict) else None


def parse_explore(files: dict[str, str]) -> Collected:
    """files：{合集目录名: index.md 全文}。没有项目的合集、解析不了的文件会被略过。"""
    nodes: list[dict[str, Any]] = []
    members: dict[str, list[str]] = {}
    used_ids: set[str] = set()
    used_labels: set[str] = set()
    for key, text in files.items():
        parsed = parse_collection(text)
        if parsed is None:
            log.warning("explore：%s 没有可解析的 YAML 头，已略过", key)
            continue
        head, body = parsed
        items = head.get("items")
        repos = list(
            dict.fromkeys(r for r in map(repo_name, items if isinstance(items, list) else []) if r)
        )
        if not repos:
            continue
        node_id = unique_slug(slugify(key), used_ids)
        name = head.get("display_name")
        label = unique_label(
            name.strip() if isinstance(name, str) and name.strip() else key, node_id, used_labels
        )
        node: dict[str, Any] = {"id": node_id, "label": label, "parent": None}
        description = first_paragraph(body)
        if description:
            node["guidance"] = {"includes": description}
        nodes.append(node)
        for repo in repos:
            members.setdefault(repo, []).append(node_id)
    meta = {
        "name": "GitHub Explore 主题合集",
        "summary": "GitHub 官方 Explore 页面上由社区贡献、GitHub 审核的主题合集（如机器学习入门、像素画工具），把相关项目收在同一个合集里。",
        "method": "curated",
        "order": 10,
        "primary": False,
        "note": "合集按主题编排而不是互斥分类，一个项目可以同时属于多个合集；合集成员里的组织主页、视频链接等非仓库条目已略去。分类说明取自合集页面的英文介绍。",
        "source": {
            "name": "GitHub Explore（github/explore）",
            "url": "https://github.com/github/explore",
            "license": "CC-BY-4.0",
            "attribution": "Content based on github.com/github/explore used under the CC-BY-4.0 license. 版权归 Explore 内容作者所有。",
        },
        "nodes": nodes,
    }
    return Collected(meta=meta, members=members)


def collect(fetcher: Fetcher) -> Collected:
    paths = list_files(fetcher, REPO, BRANCH, COLLECTION_PATH)
    texts = fetcher.texts([raw_url(REPO, BRANCH, p) for p in paths])
    files = {p.split("/")[1]: t for p, t in zip(paths, texts, strict=True)}
    collected = parse_explore(files)
    if not collected.meta["nodes"]:
        raise SourceError("github/explore 的合集里一个项目都没解析出来（文件格式可能变了）")
    log.info("explore：%d 个合集，%d 个项目", len(collected.meta["nodes"]), len(collected.members))
    return collected
