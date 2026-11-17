"""读取 2.0.9 的日常日志 / 出招记录，生成进度与战斗摘要。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class LogEvent:
    time: str
    text: str


@dataclass(slots=True)
class DailySummary:
    start: str | None = None
    end: str | None = None
    logins: list[str] = field(default_factory=list)
    areas: list[int] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    battles: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    events: int = 0

    def as_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "events": self.events,
            "logins": self.logins,
            "areas": sorted(set(self.areas)),
            "items": self.items[-30:],
            "battles": self.battles,
            "errors": self.errors,
        }


_TIME_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s?(.*)$")
_AREA_RE = re.compile(r"\[(\d+)\]区")


def parse_daily_log(path: str | Path) -> list[LogEvent]:
    raw = Path(path).read_bytes()
    for enc in ("gbk", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("gbk", "replace")
    out: list[LogEvent] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _TIME_RE.match(line)
        if m:
            out.append(LogEvent(m.group(1), m.group(2)))
        else:
            out.append(LogEvent("", line))
    return out


def summarize(events: list[LogEvent]) -> DailySummary:
    s = DailySummary(events=len(events))
    for e in events:
        t = e.text
        if not s.start and "日常开始" in t:
            s.start = e.time
        if "全部完成" in t:
            s.end = e.time
        if "登录成功" in t:
            s.logins.append(t)
            m = _AREA_RE.search(t)
            if m:
                s.areas.append(int(m.group(1)))
        if t.startswith("获得道具") or t.startswith("获得精灵") or t.startswith("获得刻印"):
            s.items.append(t)
        if "对战结束" in t or t.startswith("【胜利】") or t.startswith("【失败】"):
            s.battles.append(t)
        if "失败" in t or "错误" in t or "异常" in t:
            if "失败次数" not in t:
                s.errors.append(t)
    return s


@dataclass(slots=True)
class TurnRecord:
    turn: int
    lines: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BattleRecord:
    timestamp: str | None = None
    player: list[int] = field(default_factory=list)
    enemy: list[int] = field(default_factory=list)
    boss_traits: list[str] = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)
    result: str | None = None
    total_turns: int | None = None

    def as_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "player": self.player,
            "enemy": self.enemy,
            "boss_traits": self.boss_traits,
            "turns": len(self.turns),
            "result": self.result,
            "total_turns": self.total_turns,
        }


def parse_battle_record(path: str | Path) -> BattleRecord:
    raw = Path(path).read_bytes()
    text = raw.decode("gbk", "replace")
    rec = BattleRecord()
    cur: TurnRecord | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if rec.timestamp is None and "年" in line and "秒" in line:
            rec.timestamp = line
            continue
        m = re.search(r"【我方精灵组】([\d\s]+)", line)
        if m:
            rec.player = [int(x) for x in m.group(1).split()]
            continue
        m = re.search(r"\(对方精灵组\)([\d\s]+)", line)
        if m:
            rec.enemy = [int(x) for x in m.group(1).split()]
            continue
        if line.startswith("BOSS特性"):
            rec.boss_traits.append(line)
            continue
        m = re.search(r"当前回合：(\d+)", line)
        if m:
            cur = TurnRecord(int(m.group(1)))
            rec.turns.append(cur)
            continue
        if "对战结束" in line:
            rec.result = "结束"
            continue
        m = re.search(r"【(胜利|失败|平局)】\s*总回合：(\d+)", line)
        if m:
            rec.result = m.group(1)
            rec.total_turns = int(m.group(2))
            continue
        if cur is not None:
            cur.lines.append(line)
    return rec