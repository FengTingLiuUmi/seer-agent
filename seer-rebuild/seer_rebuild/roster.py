# -*- coding: utf-8 -*-
"""roster.py —— 只读导出玩家全部精灵个体（三处存储），统一数据契约。

契约（知识侧 SSOT 由本体 JOIN，不在这里内嵌 name/type/role/克制）：
    每行 = { uid, kind:"pet", species_id:int, catch_time:int, location:bag|elite|normal }

- species_id 即本体 seer:seerapiId（物种唯一键）
- catch_time  即个体唯一键（同一物种可多只）
- location    原始存储位置（bag=43706 背包 / elite=2361 精英仓库 / normal=2303 普通仓库）
- 跨仓可能重复（同一 catch 出现在 bag 与 elite flag=1），由消费方按 (species_id, catch_time) 去重。

背包(43706)用 pets.read_bag：43706 一次响应只带部分详情，需 43706 + 45963 推送合并才完整
（正式 + 待命）。精英仓库(2361)、普通仓库(2303 分页) 直接读。

只读；不写任何东西。
"""
from __future__ import annotations

import asyncio
import struct

from .commands import Cmd
from .connection import open_unity
from .pets import read_bag


def _parse_2361(body: bytes) -> list[tuple[int, int, int]]:
    if len(body) < 4:
        return []
    n = struct.unpack_from(">I", body, 0)[0]
    out = []
    for k in range(n):
        off = 4 + k * 12
        if off + 12 > len(body):
            break
        sp, fl, ct = struct.unpack_from(">III", body, off)
        if 1 <= sp <= 6000:
            out.append((sp, fl, ct))
    return out


def _parse_2303(body: bytes) -> list[tuple[int, int, int]]:
    if len(body) < 4:
        return []
    n = struct.unpack_from(">I", body, 0)[0]
    out = []
    for k in range(n):
        off = 4 + k * 16
        if off + 16 > len(body):
            break
        sp, fl, ct, lv = struct.unpack_from(">IIII", body, off)
        if 1 <= sp <= 6000:
            out.append((sp, ct, lv))
    return out


async def _req(c, cmd: int, body: bytes, timeout: float = 8.0) -> bytes:
    await c.send(cmd, [body] if body else [])
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == cmd:
            return f.body
    return b""


async def _read_elite_normal(account: str, password: str) -> list[dict]:
    c = await open_unity(str(account), str(password), timeout=25.0)
    try:
        rows: list[dict] = []
        for sp, fl, ct in _parse_2361(await _req(c, Cmd.GET_LOVE_PET_LIST, b"")):
            rows.append({"species_id": sp, "catch_time": ct, "location": "elite"})
        for off in (0, 1000, 2000, 3000):
            body = await _req(c, Cmd.GET_PET_LIST, struct.pack(">II", off, 1000))
            parsed = _parse_2303(body)
            for sp, ct, lv in parsed:
                rows.append({"species_id": sp, "catch_time": ct, "location": "normal", "level": lv})
            if len(parsed) < 1000:
                break
        return rows
    finally:
        await c.close()


def read_roster(account, password) -> list[dict]:
    """返回 [{species_id, catch_time, location}]（三处并集，可能含跨仓重复）。"""
    rows: list[dict] = []

    # 背包：43706 + 45963 合并，完整覆盖 正式 + 待命
    bag = read_bag(account, password, resolve_names=False)
    for grp in ("正式", "待命"):
        for p in bag.get(grp, []):
            rows.append({"species_id": p["species_id"], "catch_time": p["catch_time"], "location": "bag"})

    # 精英仓库 + 普通仓库
    rows.extend(asyncio.run(_read_elite_normal(account, password)))
    return rows


def read_levels(account, password, catch_times) -> dict:
    """只读：单连接批量读多个个体的等级（2301 S2C 0x24）。返回 {catch_time: level|None}。

    必须单连接批量（一次登录读多只），逐只 open_unity 会被服务端重置连接。
    """
    async def _run() -> dict:
        c = await open_unity(str(account), str(password), timeout=25.0)
        out = {}
        try:
            for ct in catch_times:
                body = await _req(c, Cmd.GET_PET_INFO, struct.pack(">I", int(ct) & 0xFFFFFFFF))
                out[int(ct)] = struct.unpack_from(">I", body, 0x24)[0] if len(body) >= 0x28 else None
        finally:
            await c.close()
        return out
    return asyncio.run(_run())


def read_level(account, password, catch_time) -> int | None:
    return read_levels(account, password, [catch_time]).get(int(catch_time))