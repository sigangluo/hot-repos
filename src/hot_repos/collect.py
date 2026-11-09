"""带缓存的批量抓取：命中有效缓存的键跳过，其余分批并发抓取，每批完成后立即写入日志。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from .cache import Fetched, Journal, utcnow

log = logging.getLogger(__name__)

Worker = Callable[[list[str]], Awaitable[dict[str, Any]]]


async def collect(
    keys: Sequence[str],
    journal: Journal,
    max_age: timedelta,
    worker: Worker,
    *,
    label: str,
    batch_size: int = 1,
    concurrency: int = 8,
    now: datetime | None = None,
) -> dict[str, Fetched]:
    """返回每个键的结果。worker 接收一批键，返回 `{键: 值}`，值可以为 None（表示确认不存在）。"""
    now = now or utcnow()
    cached = journal.load()
    result = {k: cached[k] for k in keys if k in cached and cached[k].is_fresh(max_age, now)}
    todo = [k for k in keys if k not in result]
    log.info("%s：%d 个命中缓存，%d 个待抓取", label, len(result), len(todo))
    if not todo:
        return result

    sem = asyncio.Semaphore(concurrency)

    async def run(batch: list[str]) -> tuple[list[str], dict[str, Any]]:
        async with sem:
            return batch, await worker(batch)

    batches = [todo[i : i + batch_size] for i in range(0, len(todo), batch_size)]
    tasks = [asyncio.ensure_future(run(b)) for b in batches]
    try:
        done = 0
        for finished in asyncio.as_completed(tasks):
            batch, values = await finished
            stamp = utcnow()
            journal.append({k: values[k] for k in batch}, stamp)
            result.update({k: Fetched(values[k], stamp) for k in batch})
            before, done = done, done + len(batch)
            if done == len(todo) or before // 250 != done // 250:
                log.info("%s：已抓取 %d/%d", label, done, len(todo))
    finally:
        for t in tasks:
            t.cancel()
    return result
