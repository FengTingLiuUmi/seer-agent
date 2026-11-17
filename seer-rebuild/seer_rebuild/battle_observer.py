"""对战观测：解析逐回合战斗帧（2408/2404/2405 + 2503/2504/2505/2506/2595/2394/2441）。

协议证据：seer-auto/cmdlog4.jsonl（官方 H5 客户端逐回合打野怪）。
本模块只做离线解析 + 图鉴反查，不负责发战斗命令。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

# C2S 战斗命令
FIGHT_NPC_MONSTER = 2408   # 发起战斗，body=[野怪id]
READY_TO_FIGHT = 2404      # 准备战斗，C2S 空 / S2C 回 4B 战斗id
USE_SKILL = 2405           # 出招，body=[技能id]
# S2C 战斗观测帧
NOTE_READY_TO_FIGHT = 2503  # 战斗初始化（双方精灵）
NOTE_START_FIGHT = 2504     # 开战·双方状态/血量
NOTE_USE_SKILL = 2505       # 技能结算
FIGHT_OVER = 2506           # 战斗结束
FIGHT_EVENT = 2595          # 战斗事件（回合动画）
LOAD_PERCENT = 2441         # 加载进度
PET_BOOK_UPDATE = 2394      # 图鉴更新

BATTLE_S2C = {NOTE_READY_TO_FIGHT, NOTE_START_FIGHT, NOTE_USE_SKILL, FIGHT_OVER, FIGHT_EVENT}
BATTLE_C2S = {FIGHT_NPC_MONSTER, READY_TO_FIGHT, USE_SKILL}


def _u32s(b: bytes) -> list[int]:
    return [struct.unpack_from(">I", b, i)[0] for i in range(0, len(b) - 3, 4)]


def _first_in(data, low=1, high=6000):
    for v in data:
        if low <= v <= high:
            return v
    return None


@dataclass(slots=True)
class BattleFrame:
    cmd: int
    body: bytes

    def describe(self, data=None) -> str:
        name = {
            FIGHT_NPC_MONSTER: "发起战斗",
            READY_TO_FIGHT: "准备战斗",
            USE_SKILL: "出招",
            NOTE_READY_TO_FIGHT: "战斗初始化",
            NOTE_START_FIGHT: "开战",
            NOTE_USE_SKILL: "技能结算",
            FIGHT_OVER: "战斗结束",
            FIGHT_EVENT: "战斗事件",
            LOAD_PERCENT: "加载进度",
            PET_BOOK_UPDATE: "图鉴更新",
        }.get(self.cmd, str(self.cmd))

        def v(off):
            return struct.unpack_from(">I", self.body, off)[0] if len(self.body) >= off + 4 else None

        def sp_name(sid):
            if data is not None and sid in data.species:
                return f"{sid}({data.species[sid].name})"
            return str(sid)

        def sk_name(sid):
            if data is not None and sid in data.moves:
                return f"{sid}({data.moves[sid].name})"
            return str(sid)

        extra = ""
        if self.cmd == USE_SKILL:
            extra = f" 技能={sk_name(v(0))}"
        elif self.cmd == FIGHT_NPC_MONSTER:
            extra = f" 野怪id={v(0)}"
        elif self.cmd == READY_TO_FIGHT and len(self.body) >= 4:
            extra = f" uid=0x{v(0):x}"
        elif self.cmd == NOTE_START_FIGHT and len(self.body) >= 0x28:
            # body 里 0x048f04a9 等是 uid 回显；野怪 species@0x0c，我方 catch@0x20，等级@0x24
            extra = (f" uid=0x{v(0x08):x} 野怪={sp_name(v(0x0c))}"
                     f" 我方catch=0x{v(0x20):x} 等级={v(0x24)}")
        elif self.cmd == NOTE_USE_SKILL and len(self.body) >= 0x1c:
            extra = (f" uid=0x{v(0):x} 技能={sk_name(v(0x04))}"
                     f" 我方catch=0x{v(0x0c):x} 伤害={v(0x18)}")
        elif self.cmd == NOTE_READY_TO_FIGHT and len(self.body) >= 0x0c:
            extra = f" uid=0x{v(0x08):x}"
        elif self.cmd == FIGHT_OVER:
            extra = f" 战斗结束(原始u32前4={[v(i) for i in range(0, min(16, len(self.body)-3), 4)]})"
        return f"[战斗] {name}{extra}"


class BattleObserver:
    """收集一次战斗的帧，输出可读的观测序列。"""

    def __init__(self, data=None):
        self.data = data
        self.frames: list[BattleFrame] = []
        self.uid: int | None = None

    def feed(self, frame) -> None:
        if frame.cmd not in BATTLE_S2C and frame.cmd not in BATTLE_C2S:
            return
        bf = BattleFrame(frame.cmd, frame.body)
        self.frames.append(bf)
        # 战斗帧 body 里 0x048f04a9 这类大数是 uid 回显（不单独当成战斗 id）
        if self.uid is None and frame.cmd in (READY_TO_FIGHT, NOTE_READY_TO_FIGHT, NOTE_START_FIGHT):
            u = _u32s(frame.body)
            for v in u:
                if 0x04000000 <= v <= 0x1FFFFFFF:
                    self.uid = v
                    break

    def describe(self) -> list[str]:
        head = f"uid=0x{self.uid:x}" if self.uid else ""
        return ([head] if head else []) + [bf.describe(self.data) for bf in self.frames]


def describe_frame(cmd: int, body: bytes, data=None) -> str:
    return BattleFrame(cmd, body).describe(data)