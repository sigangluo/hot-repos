"""断点续跑所需的缓存：原子写文件、带时间戳的缓存、追加式日志。"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Fetched:
    """一次抓取的结果及其获取时间。"""

    value: Any
    fetched_at: datetime

    def is_fresh(self, max_age: timedelta, now: datetime) -> bool:
        return now - self.fetched_at <= max_age


def utcnow() -> datetime:
    return datetime.now(UTC)


def write_json(path: Path, value: Any, *, indent: int | None = None, compact: bool = False) -> None:
    """先写临时文件再替换，中断时不会留下半截文件。`compact` 去掉分隔符后的空格，用于体积敏感的文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(
        value, ensure_ascii=False, indent=indent, separators=(",", ":") if compact else None
    )
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, path)


def save_stamped(path: Path, value: Any, fetched_at: datetime) -> None:
    write_json(path, {"fetched_at": fetched_at.isoformat(), "value": value})


def load_stamped(path: Path) -> Fetched | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Fetched(raw["value"], datetime.fromisoformat(raw["fetched_at"]))


class Journal:
    """追加式日志（JSON Lines），每行一条 `{"key", "fetched_at", "value"}`，同键以最后一条为准。

    长任务每完成一批就追加一次；崩溃留下的半行在下次读取时被忽略。
    """

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Fetched]:
        entries: dict[str, Fetched] = {}
        if not self.path.exists():
            return entries
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                entries[raw["key"]] = Fetched(
                    raw["value"], datetime.fromisoformat(raw["fetched_at"])
                )
            except (ValueError, KeyError):
                log.warning("忽略 %s 中被中断的记录", self.path.name)
        return entries

    def append(self, values: dict[str, Any], fetched_at: datetime) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = fetched_at.isoformat()
        with self.path.open("a", encoding="utf-8") as f:
            f.write("\n")  # 前导换行把上次中断的半行隔开
            for key, value in values.items():
                f.write(
                    json.dumps(
                        {"key": key, "fetched_at": stamp, "value": value}, ensure_ascii=False
                    )
                )
                f.write("\n")
            f.flush()

    def compact(self, retention: timedelta | None = None, now: datetime | None = None) -> None:
        """只保留每个键的最新记录；给出 `retention` 时，再丢弃比它更旧的记录。

        后者用来清掉已不会再被用到的键（例如周 Star 分布里按“第一页最新周”区分的旧页）。
        """
        now = now or utcnow()
        entries = {
            k: e for k, e in self.load().items() if retention is None or e.is_fresh(retention, now)
        }
        if not entries:
            self.path.unlink(missing_ok=True)
            return
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for key, e in entries.items():
                record = {"key": key, "fetched_at": e.fetched_at.isoformat(), "value": e.value}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)
