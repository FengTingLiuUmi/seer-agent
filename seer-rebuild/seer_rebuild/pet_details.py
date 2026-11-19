"""单精灵个体详情（2301）解析 + 能力值读取。

2301 布局（已从深渊狱神·哈迪斯个体 calib）：
  0x00 species_id
  0x20+  经验/零区
  0x24  level
  0x34  体力(当前)  0x38 体力(满)
  0x3c  物攻      0x40 物防
  0x44  特攻      0x48 特防
  0x4c  速度
  0x6c+8*i  装备技能 id（i=0..4，共 5 个技能槽）

能力值 = 基础 + 个体值 + 学习力 ± 性格 ± 刻印 + 装备 + 称号，2301 给的已是最终值。
"""
from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field


def u32_at(b: bytes, off: int) -> int:
    return struct.unpack_from(">I", b, off)[0] if len(b) >= off + 4 else 0


@dataclass(slots=True)
class PetDetail:
    species_id: int
    level: int
    max_hp: int
    cur_hp: int
    atk: int
    def_: int
    sp_atk: int
    sp_def: int
    spd: int
    skills: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "species_id": self.species_id, "level": self.level,
            "能力值": {"体力": self.max_hp, "当前体力": self.cur_hp, "物攻": self.atk,
                        "物防": self.def_, "特攻": self.sp_atk, "特防": self.sp_def, "速度": self.spd},
            "装备技能": self.skills,
        }


def parse_2301(body: bytes) -> PetDetail:
    return PetDetail(
        species_id=u32_at(body, 0x00),
        level=u32_at(body, 0x24),
        max_hp=u32_at(body, 0x38),
        cur_hp=u32_at(body, 0x34),
        atk=u32_at(body, 0x3c),
        def_=u32_at(body, 0x40),
        sp_atk=u32_at(body, 0x44),
        sp_def=u32_at(body, 0x48),
        spd=u32_at(body, 0x4c),
        skills=[u32_at(body, 0x6c + i * 8) for i in range(5) if u32_at(body, 0x6c + i * 8)],
    )


def read_pet_detail(account: str, password: str, catch_time: int, *, timeout: float = 20.0) -> PetDetail | None:
    """登录并读某个体(catch_time)的 2301 详情。只读。"""
    from .connection import open_unity

    async def _run() -> PetDetail | None:
        c = await open_unity(account, password, timeout=timeout)
        await c.send(2301, [struct.pack(">I", catch_time & 0xFFFFFFFF)])
        loop = asyncio.get_running_loop()
        end = loop.time() + 6.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=0.8)
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2301:
                await c.close()
                return parse_2301(f.body)
        await c.close()
        return None

    return asyncio.run(_run())