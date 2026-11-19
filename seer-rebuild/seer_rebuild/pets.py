"""精灵背包：读列表 + 仓库/背包互转（基于 petbag/petbag2/Wireshark 抓包）。

命令（Unity 端，账号 ACCOUNT）：
  - 读精灵：登录(1001)+心跳(1002) → `1016 GET_SESSION_KEY`(body=u32(2)) → `43706 GET_PET_INFO_BY_ONCE`(空)
  - 精灵列表(S2C)：`2361` 响应 = `[count u32] + N×[species_id, flag, catch_time]`（flag=1 表示首发）
  - 仓库/背包移动：`2304 PET_RELEASE` = `[pet_runtime_id u32][flag u32]`（0=放回仓库 1=加入背包）
  - 单精灵详情：`2301` 响应 body 第一个 u32 = species_id

runtime_id 与 species_id 经 `2301` 转换；`2361` 列表直接给 species_id，可直接反查名称。
"""
from __future__ import annotations

import asyncio
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from .commands import Cmd
from .connection import open_unity
from .protocol import Frame

# 背包(战斗背包)详情：43706 响应，第一个 u32 = count（当前背包精灵数）。
# 每只精灵详情结构（变长）：species_id(4B) + 技能序列 + runtime_id(4B，0x5~0x6 开头随机)
#   + 属性字段 + catch_time(unix)。实测识别到：
#     帝皇之御 3512 → runtime 0x602211ae；圣灵谱尼 5000 → runtime 0x57c55a7f。
# 一个 43706 响应 body 约只携带 2 只完整详情；count>2 时其余精灵走 2301 逐个查。


@dataclass(slots=True)
class PetEntry:
    species_id: int #精灵图鉴id
    flag: int #操作
    catch_time: int #精灵获得时间 其实就是赛尔号检测重复精灵的标识

    @property
    def is_starter(self) -> bool:
        return self.flag == 1


def release_body(pet_runtime_id: int, flag: int) -> bytes:
    """仓库/背包移动 body：pet runtime id + flag（实测 0=放回仓库, 1=加入背包）。"""
    return struct.pack(">II", pet_runtime_id & 0xFFFFFFFF, flag & 0xFFFFFFFF)


def parse_pet_list(body: bytes) -> list[PetEntry]:
    """解析 2361（仓库）响应：`[count] + N×[species_id, flag, catch_time]`。"""
    if len(body) < 4:
        return []
    count = struct.unpack_from(">I", body, 0)[0]
    pets: list[PetEntry] = []
    for k in range(count):
        off = 4 + k * 12
        if off + 12 > len(body):
            break
        species = struct.unpack_from(">I", body, off)[0]
        flag = struct.unpack_from(">I", body, off + 4)[0]
        catch = struct.unpack_from(">I", body, off + 8)[0]
        if not (1 <= species <= 6000):
            continue
        pets.append(PetEntry(species, flag, catch))
    return pets


def parse_warehouse_list(body: bytes) -> list[PetEntry]:
    """别名：仓库列表（=2361）。"""
    return parse_pet_list(body)


def parse_bag_45963(body: bytes, data: Any | None = None) -> PetEntry | None:
    """解析 45963（背包单只精灵推送）响应。

结构（固定偏移，已从 wsbag 抓包验证）：
  - 0x08 精灵名(UTF-8 变长)
  - 0x34 catch_time(u32)
  - 0x74 species_id(u32)
返回 PetEntry(species_id, flag=0, catch_time)。
"""
    if len(body) < 0x78:
        return None
    species = struct.unpack_from(">I", body, 0x74)[0]
    catch = struct.unpack_from(">I", body, 0x34)[0]
    if not (1 <= species <= 6000):
        return None
    if data is not None and species not in getattr(data, "species", {species: None}):
        return None
    return PetEntry(species, 0, catch)


def _is_catch_time(v: int) -> bool:
    """unix 秒（约 2015-01-01 ~ 2027-01-01）。"""
    return 0x54A00000 <= v <= 0x6C000000


def parse_bag_43706(body: bytes, data: Any | None = None) -> tuple[int, list[PetEntry]]:
    """解析 43706（背包）响应。

结构：`[count u32] + 每只精灵详情`，每只详情里 species 在块开头、catch_time 在
species 之后 0x94(148) 字节处。用「species + 148B 后是 catch_time」识别每只。

返回 (count, [PetEntry(species, flag=0, catch_time)])。data 可选（本地图鉴，用于校验 species 合法）。
"""
    if len(body) < 4:
        return 0, []
    count = struct.unpack_from(">I", body, 0)[0]
    span = 0x94
    out: list[PetEntry] = []
    seen: set[int] = set()
    known = getattr(data, "species", None) if data is not None else None
    for off in range(0, len(body) - span - 4):  # 逐字节：块首非 4 对齐
        species = struct.unpack_from(">I", body, off)[0]
        if not (1 <= species <= 6000):
            continue
        if known is not None and species not in known:
            continue
        # 块首特征：species 后 8 字节为零填充
        if body[off + 4:off + 12] != b"\x00" * 8:
            continue
        catch = struct.unpack_from(">I", body, off + span)[0]
        if not _is_catch_time(catch):
            continue
        if (catch & 0xFFFF) == 0:  # 排除 bitfield 对齐值被误判成 catch
            continue
        if catch in seen:
            continue
        seen.add(catch)
        out.append(PetEntry(species, 0, catch))
    return count, out


async def _send_and_collect(account: str, password: str, send_specs: list[tuple[int, bytes]], *, wait: float = 4.0) -> tuple[int, list[dict]]:
    c = await open_unity(account, password)
    uid = c.session.uid
    collected: list[dict] = []

    def add(f: Frame) -> None:
        collected.append({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body.hex()})

    loop = asyncio.get_running_loop()
    for cmd, body in send_specs:
        try:
            await c.send(cmd, [body] if body else [])
        except (ConnectionError, asyncio.IncompleteReadError):
            break
        end = loop.time() + wait
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            add(f)
    await c.close()
    return uid, collected


def _u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def read_bag(account: str, password: str, *, resolve_names: bool = True) -> dict:
    """在线读背包：登录(含会话握手) → 46046+43706 → token 轮询收集 43706 详情 + 45963 推送 → 合并去重。

背包精灵来源两处：
  - 43706 响应：携带部分精灵完整详情（species 各块开头 + catch@+0x94）
  - 45963 响应：每只精灵一条推送（species@0x74, catch@0x34）
合并去重后得到完整背包清单。
"""
    async def _run() -> dict:
        from .battle_data import BattleData
        data = BattleData(r"F:\seer\seer_cfg\json")

        c = await open_unity(account, password)
        uid = c.session.uid
        loop = asyncio.get_running_loop()

        await c.send(Cmd.GET_PET_INFO_BY_ONCE, [])  # 一次性读背包（正式 + 待命）

        # 只取第一个 43706 响应；按 body 头部计数区分「正式 / 待命」。
        formal: list[PetEntry] = []
        reserve: list[PetEntry] = []
        end = loop.time() + 12.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == Cmd.GET_PET_INFO_BY_ONCE:
                cnt, pets = parse_bag_43706(f.body, data=data)
                formal = pets[:cnt]
                reserve = pets[cnt:]
                break

        await c.close()

        def fmt(p: PetEntry) -> dict:
            d = {"species_id": p.species_id, "catch_time": p.catch_time}
            if resolve_names:
                sp = data.species.get(p.species_id)
                d["name"] = sp.name if sp else str(p.species_id)
            return d

        return {
            "uid": uid,
            "正式": [fmt(p) for p in formal],
            "待命": [fmt(p) for p in reserve],
        }

    return asyncio.run(_run())


def format_bag_text(bag: dict) -> str:
    """把 read_bag 的结果格式化成纯文本。"""
    lines = [f"uid: {bag.get('uid')}"]
    for group in ("正式", "待命"):
        pets = bag.get(group, [])
        lines.append(f"[{group}] {len(pets)} 只")
        for p in pets:
            name = p.get("name") or str(p.get("species_id"))
            lines.append(f"  {name}（species={p.get('species_id')} catch_time={p.get('catch_time')}）")
    return "\n".join(lines)


def move_pet(account: str, password: str, pet_catch_time: int, *, to_bag: bool, out_path: str | Path | None = None) -> dict:
    """加入背包(to_bag=True, flag=1) 或 放回仓库(to_bag=False, flag=0)。用 catch_time 定位精灵个体。"""
    flag = 1 if to_bag else 0
    body = release_body(pet_catch_time, flag)
    specs = [(Cmd.GET_SESSION_KEY, b"\x00\x00\x00\x02"), (Cmd.GET_PET_INFO_BY_ONCE, b""), (Cmd.PET_RELEASE, body)]
    uid, frames = asyncio.run(_send_and_collect(account, password, specs))
    if out_path:
        Path(out_path).write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in frames) + "\n", encoding="utf-8")
    return {"uid": uid, "pet_catch_time": pet_catch_time, "to_bag": to_bag, "body": body.hex(), "frames": frames}


