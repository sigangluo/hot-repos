"""命令行入口：`hot-repos fetch` 采集总榜、`trending` 采集 Trending、`schemes sync` 同步外部分类体系、`validate` 校验、`export` 导出页面数据。"""

import argparse
import asyncio
import logging
import sys
from datetime import timedelta
from pathlib import Path

from . import config, export_web, sync, trending
from .github.client import GitHubClient, GitHubError, get_token
from .github.trending import TrendingError
from .pipeline import DataError, Options, run
from .sources import Fetcher, SourceError
from .validate import validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hot-repos", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="采集总榜、元数据和周 Star 分布，更新 data/")
    fetch.add_argument("-n", "--top", type=_positive_int, required=True, help="总榜名额，例如 5000")
    fetch.add_argument(
        "--max-age-hours",
        type=_non_negative_float,
        default=config.DEFAULT_MAX_AGE_HOURS,
        help="缓存有效时长（小时），超过则重新抓取（默认 %(default)s）",
    )
    fetch.add_argument("--refresh", action="store_true", help="忽略缓存，全部重新抓取")
    fetch.add_argument(
        "--star-weeks",
        choices=["recent", "full", "skip"],
        default="recent",
        help="周 Star 分布：recent 取最近一页（默认），full 取全部历史，skip 沿用 data/ 中已有的",
    )
    fetch.add_argument(
        "--rps", type=float, default=config.REQUESTS_PER_SECOND, help="每秒请求数上限"
    )
    fetch.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    fetch.add_argument("--cache-dir", type=Path, default=config.CACHE_DIR)

    trend = sub.add_parser("trending", help="抓取 GitHub Trending，写入 data/trending/ 当天的快照")
    trend.add_argument(
        "--rps",
        type=_positive_float,
        default=config.TRENDING_REQUESTS_PER_SECOND,
        help="每秒请求数上限（默认 %(default)s）",
    )
    trend.add_argument("--data-dir", type=Path, default=config.DATA_DIR)

    schemes = sub.add_parser("schemes", help="分类体系：同步别人已经做好的公开分类")
    schemes_sub = schemes.add_subparsers(dest="schemes_command", required=True)
    sync_cmd = schemes_sub.add_parser(
        "sync", help="从公开来源取分类，把总榜里的项目对上去，写入 data/schemes/"
    )
    sync_cmd.add_argument(
        "ids", nargs="*", help="要同步的来源编号（默认全部），如 borges cncf；见 docs/schemes.md"
    )
    sync_cmd.add_argument("--data-dir", type=Path, default=config.DATA_DIR)

    export = sub.add_parser("export", help="把 data/ 导出为页面用的数据文件")
    export.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    export.add_argument("--out-dir", type=Path, default=config.WEB_DATA_DIR)

    check = sub.add_parser("validate", help="校验 data/ 的完整性与一致性")
    check.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    return parser


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("应为正整数")
    return n


def _positive_float(value: str) -> float:
    x = float(value)
    if x <= 0:
        raise argparse.ArgumentTypeError("应为正数")
    return x


def _non_negative_float(value: str) -> float:
    x = float(value)
    if x < 0:
        raise argparse.ArgumentTypeError("不能为负数")
    return x


async def _fetch(args: argparse.Namespace) -> None:
    opts = Options(
        n=args.top,
        data_dir=args.data_dir,
        cache_dir=args.cache_dir,
        max_age=timedelta(0) if args.refresh else timedelta(hours=args.max_age_hours),
        star_weeks=args.star_weeks,
    )
    async with GitHubClient(get_token(), rps=args.rps) as client:
        await run(opts, client)


async def _trending(args: argparse.Namespace) -> None:
    async with GitHubClient(None, rps=args.rps) as client:
        await trending.run(client, args.data_dir / config.TRENDING_DIR_NAME)


def _schemes_sync(args: argparse.Namespace) -> int:
    try:
        token: str | None = get_token()
    except GitHubError:  # 没有 Token 也能同步，只是 GitHub 接口的额度更低
        token = None
    results = sync.run(args.data_dir, args.ids, Fetcher(token))
    for scheme_id, text in results.items():
        print(f"{scheme_id}: {text}")
    return 1 if any(t.startswith("失败") for t in results.values()) else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        if args.command == "fetch":
            asyncio.run(_fetch(args))
        elif args.command == "trending":
            asyncio.run(_trending(args))
        elif args.command == "schemes":
            return _schemes_sync(args)
        elif args.command == "export":
            for name, size in export_web.export(args.data_dir, args.out_dir).items():
                print(f"{args.out_dir / name}  {size / 1024:.0f} KB")
        else:
            problems = validate(args.data_dir)
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            print("数据校验通过")
    except (GitHubError, TrendingError, DataError, SourceError, export_web.ExportError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
