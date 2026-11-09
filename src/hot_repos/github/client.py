"""GitHub HTTP 客户端：请求节流、限流等待、网络错误与服务端错误重试。"""

import asyncio
import logging
import os
import subprocess
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Self

import httpx

from .. import config

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 10
MAX_RATE_LIMIT_WAITS = 200
SERVER_ERRORS = (500, 502, 503, 504)

Sleep = Callable[[float], Awaitable[None]]


class GitHubError(RuntimeError):
    """重试耗尽或遇到不可恢复的错误。已写入缓存的进度保留，重跑即可续上。"""


def get_token() -> str:
    """依次读取环境变量 GITHUB_TOKEN / GH_TOKEN 和 `gh auth token`，只保存在内存中。"""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        return subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise GitHubError(
            "未找到 GitHub Token：请设置 GITHUB_TOKEN，或先执行 `gh auth login`"
        ) from e


class Pacer:
    """把请求均匀分布在时间轴上，所有并发任务共用同一个。"""

    def __init__(self, interval: float, sleep: Sleep = asyncio.sleep):
        self.interval = interval
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._next_at - time.monotonic()
            if delay > 0:
                await self._sleep(delay)
            self._next_at = max(self._next_at, time.monotonic()) + self.interval

    def pause(self, seconds: float) -> None:
        """限流时让所有后续请求一起等待。"""
        self._next_at = max(self._next_at, time.monotonic() + seconds)


def rate_limit_wait(response: httpx.Response, now: float | None = None) -> float | None:
    """判断响应是否为限流，是则返回建议等待的秒数，否则返回 None。"""
    if response.status_code not in (403, 429):
        return None
    headers = response.headers
    primary = headers.get("x-ratelimit-remaining") == "0"
    retry_after = headers.get("retry-after")
    text = response.text.lower()
    if not (primary or retry_after or "rate limit" in text or "secondary" in text):
        return None
    wait = 1.0 if primary else 60.0
    if retry_after:
        wait = max(wait, float(retry_after))
    if primary:
        reset = float(headers.get("x-ratelimit-reset", 0))
        wait = max(wait, reset - (now if now is not None else time.time()) + 2)
    return wait


def _is_json(response: httpx.Response) -> bool:
    try:
        response.json()
    except ValueError:
        log.warning(
            "响应正文不是合法 JSON（%d 字节），重试：%s", len(response.content), response.url
        )
        return False
    return True


class GitHubClient:
    """所有 GitHub 请求的唯一出口。

    `token` 为 None 时不带任何认证信息，用于抓取不需要登录的网页（如 Trending），避免把 Token 发给网页。
    """

    def __init__(
        self,
        token: str | None,
        *,
        rps: float = config.REQUESTS_PER_SECOND,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ):
        self.sleep = sleep
        self.pacer = Pacer(1 / rps, sleep)
        self.search_pacer = Pacer(config.SEARCH_INTERVAL_SECONDS, sleep)
        self.requests = 0
        headers = {"User-Agent": "hot-repos"}
        if token is not None:
            headers |= {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        self._http = httpx.AsyncClient(
            headers=headers,
            transport=transport,
            follow_redirects=True,
            timeout=90,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=64),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        extra_pacer: Pacer | None = None,
        retry_statuses: Iterable[int] = (),
        max_attempts: int = MAX_ATTEMPTS,
        expect_json: bool = False,
    ) -> httpx.Response:
        """发送请求并返回响应。

        网络错误、5xx 和 `retry_statuses` 中的状态码最多尝试 `max_attempts` 次；
        `expect_json` 为真时，200 响应的正文必须是合法 JSON，否则（偶发的空正文或错误页）同样重试。
        限流则一直等到额度恢复（至多 MAX_RATE_LIMIT_WAITS 次），不占用尝试次数。
        其余状态码（含 404）原样返回，由调用方判断。
        """
        retry = {*SERVER_ERRORS, *retry_statuses}
        attempt = rate_limited = 0
        while attempt < max_attempts:
            if extra_pacer:
                await extra_pacer.wait()
            await self.pacer.wait()
            try:
                response = await self._http.request(
                    method, url, params=params, json=json, headers=headers
                )
            except httpx.HTTPError as e:
                self.requests += 1
                attempt += 1
                log.warning(
                    "请求失败（%s），重试 %d/%d：%s", type(e).__name__, attempt, max_attempts, url
                )
                await self.sleep(min(30, 2**attempt))
                continue
            self.requests += 1
            wait = rate_limit_wait(response)
            if wait is not None:
                rate_limited += 1
                if rate_limited > MAX_RATE_LIMIT_WAITS:
                    break
                log.warning("触发 GitHub 限流，等待 %d 秒后重试", wait)
                self.pacer.pause(wait)
                continue
            if response.status_code in retry or (
                expect_json and response.status_code == 200 and not _is_json(response)
            ):
                attempt += 1
                await self.sleep(min(30, 2**attempt))
                continue
            return response
        raise GitHubError(f"重试多次仍失败：{method} {url}；已缓存的进度保留，重跑即可续上")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)
