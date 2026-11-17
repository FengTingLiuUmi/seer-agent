"""进度与观测：任务状态、事件日志、战报输出。"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class TaskRecord:
    name: str
    state: TaskState = TaskState.PENDING
    started_at: float | None = None
    finished_at: float | None = None
    detail: str = ""
    error: str = ""
    items: list[str] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        return (self.finished_at or time.time()) - self.started_at


class ProgressTracker:
    def __init__(self, *, log_path: str | Path | None = None):
        self.records: dict[str, TaskRecord] = {}
        self.order: list[str] = []
        self.log_path = Path(log_path) if log_path else None
        self.lines: list[str] = []

    def add(self, name: str) -> TaskRecord:
        r = self.records.get(name)
        if r is None:
            r = TaskRecord(name)
            self.records[name] = r
            self.order.append(name)
        return r

    def start(self, name: str) -> None:
        r = self.add(name)
        r.state = TaskState.RUNNING
        r.started_at = time.time()
        self._log(f"[开始] {name}")

    def update(self, name: str, detail: str, *, item: str | None = None) -> None:
        r = self.add(name)
        r.detail = detail
        if item:
            r.items.append(item)
        self._log(f"[进度] {name}: {detail}")

    def complete(self, name: str, detail: str = "") -> None:
        r = self.add(name)
        r.state = TaskState.DONE
        r.finished_at = time.time()
        r.detail = detail or r.detail
        self._log(f"[完成] {name} {detail}")

    def fail(self, name: str, error: str) -> None:
        r = self.add(name)
        r.state = TaskState.FAILED
        r.finished_at = time.time()
        r.error = error
        self._log(f"[失败] {name}: {error}")

    def skip(self, name: str, reason: str = "") -> None:
        r = self.add(name)
        r.state = TaskState.SKIPPED
        r.detail = reason
        self._log(f"[跳过] {name} {reason}")

    def _log(self, line: str) -> None:
        self.lines.append(line)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def snapshot(self) -> dict[str, Any]:
        return {
            "tasks": [
                {
                    "name": n,
                    "state": self.records[n].state.value,
                    "detail": self.records[n].detail,
                    "error": self.records[n].error,
                    "elapsed": round(self.records[n].elapsed, 2),
                }
                for n in self.order
            ],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")

    def write_markdown(self, path: str | Path) -> None:
        lines = ["# 日常进度", "", f"更新时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "", "| 任务 | 状态 | 耗时(s) | 说明 |", "|---|---|---:|---|"]
        for n in self.order:
            r = self.records[n]
            lines.append(f"| {n} | {r.state.value} | {r.elapsed:.1f} | {r.detail or r.error} |")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class Observer:
    """统一事件总线；CLI/战报/进度都向它订阅。"""

    def __init__(self):
        self.handlers: list[Callable[[str, dict], None]] = []

    def subscribe(self, fn: Callable[[str, dict], None]) -> None:
        self.handlers.append(fn)

    def emit(self, kind: str, payload: dict) -> None:
        for fn in self.handlers:
            try:
                fn(kind, payload)
            except Exception:
                pass