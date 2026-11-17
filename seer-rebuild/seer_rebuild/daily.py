"""日常处理框架与内置任务。

2.0.9 的“一键日常”由主程序内置 + ``seer_cfg/DLL/center/*.dll`` 插件组成。
本模块复刻的是可验证的骨架：
  * 读取 ``一键日常ACCOUNT.ini`` 的开关；
  * 任务注册/进度/重试/观测；
  * 已确认 cmdID 的只读/领奖任务（见 seer-auto/data/commandid.json）；
  * 未确认的任务以 CommandTask 形式保留，必须显式启用。

所有写操作默认 ``dry_run=True``，只打印将要发送的帧；确认账号与协议后再关闭。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from .client import GameClient
from .ini_util import as_bool, as_int, load_ini
from .progress import Observer, ProgressTracker
from .protocol import Frame


@dataclass(slots=True)
class AppDailyConfig:
    path: Path | None = None
    values: dict[str, str] = field(default_factory=dict)

    def enabled(self, key: str, default: bool = False) -> bool:
        return as_bool(self.values.get(key), default)

    def value(self, key: str, default: int = 0) -> int:
        return as_int(self.values.get(key), default)


def load_app_daily_config(path: str | Path) -> AppDailyConfig:
    p = Path(path)
    doc = load_ini(p)
    values: dict[str, str] = {}
    for _, kv in doc.sections:
        values.update(kv)
    return AppDailyConfig(path=p, values=values)


@dataclass(slots=True)
class TaskContext:
    client: GameClient
    session: Any
    progress: ProgressTracker
    observer: Observer
    config: AppDailyConfig | None = None
    dry_run: bool = True
    params: dict[str, Any] = field(default_factory=dict)


class DailyTask:
    name = "task"
    requires_write = False

    async def run(self, ctx: TaskContext) -> str:
        raise NotImplementedError


class CommandTask(DailyTask):
    def __init__(
        self,
        name: str,
        cmd: int,
        args: list[Any] | None = None,
        *,
        expect: int | None = None,
        timeout: float = 10.0,
        parser: Callable[[Frame], str] | None = None,
        requires_write: bool = False,
    ):
        self.name = name
        self.cmd = cmd
        self.args = args or []
        self.expect = expect if expect is not None else cmd
        self.timeout = timeout
        self.parser = parser
        self.requires_write = requires_write

    async def run(self, ctx: TaskContext) -> str:
        if self.requires_write and ctx.dry_run:
            return f"dry-run: would send cmd={self.cmd} args={self.args!r}"
        f = await ctx.client.request(self.cmd, self.args, timeout=self.timeout)
        detail = f"cmd={self.cmd} result={f.result} body={f.body[:64].hex()}"
        if self.parser:
            detail += " | " + self.parser(f)
        ctx.observer.emit("frame", {"cmd": f.cmd, "result": f.result, "body": f.body.hex()})
        return detail


class ObserveTask(DailyTask):
    """观察 N 秒内的所有帧，输出可读摘要；不发包。"""

    name = "observe"
    requires_write = False

    def __init__(self, seconds: float = 10.0):
        self.seconds = seconds

    async def run(self, ctx: TaskContext) -> str:
        end = asyncio.get_running_loop().time() + self.seconds
        count = 0
        while asyncio.get_running_loop().time() < end:
            try:
                f = await asyncio.wait_for(ctx.client.next_frame(), timeout=min(1.0, end - asyncio.get_running_loop().time()))
            except asyncio.TimeoutError:
                continue
            count += 1
            text = _decode_body(f.body)
            ctx.observer.emit("frame", {"cmd": f.cmd, "result": f.result, "body": f.body.hex(), "text": text})
            ctx.progress.update(self.name, f"cmd={f.cmd} len={len(f.body)} {text[:80]}")
        return f"observed {count} frames in {self.seconds}s"


def _decode_body(body: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            s = body.decode(enc)
            if all(c.isprintable() or c in "\r\n\t" for c in s):
                return s
        except UnicodeDecodeError:
            pass
    return body.hex()


class DailyRunner:
    def __init__(
        self,
        tasks: list[DailyTask],
        *,
        progress: ProgressTracker | None = None,
        observer: Observer | None = None,
        dry_run: bool = True,
        retries: int = 1,
        stop_on_error: bool = False,
    ):
        self.tasks = tasks
        self.progress = progress or ProgressTracker()
        self.observer = observer or Observer()
        self.dry_run = dry_run
        self.retries = retries
        self.stop_on_error = stop_on_error

    async def run(self, ctx: TaskContext) -> ProgressTracker:
        ctx.progress = self.progress
        ctx.observer = self.observer
        ctx.dry_run = self.dry_run
        for task in self.tasks:
            self.progress.start(task.name)
            last_error = None
            for attempt in range(self.retries + 1):
                try:
                    detail = await task.run(ctx)
                    self.progress.complete(task.name, detail)
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    self.progress.update(task.name, f"第 {attempt + 1} 次尝试失败: {e}")
                    await asyncio.sleep(min(2.0, 0.2 * (attempt + 1)))
            if last_error is not None:
                self.progress.fail(task.name, str(last_error))
                if self.stop_on_error:
                    break
        return self.progress


# ---------------------------------------------------------------------------
# 常用任务工厂
# 说明：cmdID 来自 seer-auto/data/commandid.json（官方客户端 CommandID 枚举）。
# 这些名字能对上，但 2.0.9 的 body 仍需抓包校准；默认 dry_run。

def builtin_tasks(*, include_write: bool = False) -> list[DailyTask]:
    tasks: list[DailyTask] = [
        CommandTask("日常信息", 8016, requires_write=False, parser=lambda f: _decode_body(f.body)),
        CommandTask("日常数值", 2707, requires_write=False, parser=lambda f: _decode_body(f.body)),
        CommandTask("勇者之塔成就", 3453, requires_write=False, parser=lambda f: _decode_body(f.body)),
    ]
    if include_write:
        tasks += [
            CommandTask("领取每日奖励", 2875, requires_write=True),
            CommandTask("领取每周奖励", 2876, requires_write=True),
            CommandTask("领取每日热门", 2877, requires_write=True),
        ]
    return tasks


def tasks_from_app_config(cfg: AppDailyConfig, *, include_write: bool = False) -> list[DailyTask]:
    """按 2.0.9 的开关生成任务列表。未映射的开关只记录，不伪造命令。"""
    mapping: list[tuple[str, DailyTask]] = [
        ("日常领取", CommandTask("日常领取", 2875, requires_write=True)),
        ("经验学习力训练", CommandTask("经验学习力训练", 2707, requires_write=False)),
        ("勇者之塔", CommandTask("勇者之塔", 3453, requires_write=False)),
    ]
    out: list[DailyTask] = []
    for key, task in mapping:
        if cfg.enabled(key):
            if include_write or not task.requires_write:
                out.append(task)
    return out


def load_task_spec(path: str | Path) -> list[DailyTask]:
    """从 JSON 载入自定义日常脚本。

    格式::

        {"tasks": [
          {"name": "日常信息", "cmd": 8016, "args": [], "expect": 8016, "write": false},
          {"name": "领奖", "cmd": 2875, "write": true}
        ]}
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks: list[DailyTask] = []
    for item in data.get("tasks", []):
        tasks.append(
            CommandTask(
                item.get("name") or f"cmd_{item['cmd']}",
                int(item["cmd"]),
                item.get("args") or [],
                expect=item.get("expect"),
                timeout=float(item.get("timeout", 10)),
                requires_write=bool(item.get("write")),
            )
        )
    return tasks