"""当前背包 / 装扮 / 装备 的数据模型与采集。

赛尔号现在把「外观」拆成两套：
  - 装扮(clothes)：纯外观，equip 中 bonus==null 的部位（head/eye/waist/hand/foot/…）
  - 装备(equipment)：真正提供属性加成，equip 中 bonus 有值的部位

数据来源：
  1. 抓包回放（feature1_frames.jsonl）：`2604 CHANGE_CLOTH`=换装扮，`42399`=道具
  2. 实时登录：Unity `1001` 快照里提取当前穿戴部位 ID
  3. 反查：SeerAPI 的 `equip` 资源给出 name + part_type(部位) + bonus(属性)
"""
from __future__ import annotations

import asyncio
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .client import GameClient
from .ini_util import load_ini
from .login import LoginSession, authenticate, authenticate_cached, get_unity_gateway
from .protocol import Frame

READ_CMDS = [43706, 46046, 42399, 2301, 41301]

# equip_type id -> 部位名（来自 seerapi equip_type 资源）
EQUIP_TYPE_NAMES = {
    0: "头部",
    1: "目镜",
    2: "腰部",
    3: "手部",
    4: "足部",
    5: "背景",
    6: "坐骑",
}

_LOCAL_EQUIP_JSON = r"F:\seer\seer_cfg\json\equip.ini"
_local_suit_cache: dict[int, int] | None = None


def _local_suit_map() -> dict[int, int]:
    """本地 equip.ini 的 SuitID 映射（seerapi equip.suit 常为 null，这里作补充）。"""
    global _local_suit_cache
    if _local_suit_cache is None:
        _local_suit_cache = {}
        try:
            doc = load_ini(_LOCAL_EQUIP_JSON)
            for sec, kv in doc.sections:
                sid = kv.get("SuitID")
                if sid and str(sid).strip() not in ("", "0"):
                    _local_suit_cache[int(sec)] = int(sid)
        except Exception:
            pass
    return _local_suit_cache


@dataclass(slots=True)
class InventoryItem:
    """道具（背包里的普通物品）。"""
    id: int            # 道具 id（seerapi `item` 资源）
    name: str = ""     # 道具名（resolve 反查后填入）
    count: int = 1     # 数量

    @property
    def label(self) -> str:
        return self.name or f"[{self.id}]"


@dataclass(slots=True)
class TitleEntry:
    """称号（独立称号栏，提供称号加成）。"""
    id: int            # 称号 id（seerapi `title` 资源）
    name: str = ""     # 称号名（resolve 反查后填入）
    bonus: str = ""    # 称号加成文本（attr_bonus/ability_desc 反查，如"攻击+60"）
    desc: str = ""     # 称号描述

    @property
    def label(self) -> str:
        return self.name or f"[{self.id}]"

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "bonus": self.bonus, "desc": self.desc}


@dataclass(slots=True)
class EquipEntry:
    """角色身上一个穿戴部位（头/目镜/腰/手/足等）。

    一个类同时承载「装备/装扮」两种含义，靠 bonus / suit_bonus 是否有值区分：
      - 装备(equipment)：真正提供属性加成（bonus 或 suit_bonus 有值）
      - 装扮(clothes) ：纯外观时装（两者皆空）
    """
    slot: str          # 部位名："头部"/"目镜"/"腰部"/"手部"/"足部"/"背景"/"坐骑"
    id: int            # 该部位穿戴的 equip id（seerapi `equip` 资源）
    name: str = ""     # 名称（resolve 反查后填入）
    bonus: str = ""    # 单件加成文本（如"物攻+30点、速度+15点"）；空=无单件加成
    suit: str = ""     # 所属套装名；空=不属于套装
    suit_bonus: str = ""  # 套装加成文本；空=该套装无加成

    @property
    def label(self) -> str:
        return self.name or f"[{self.id}]"

    @property
    def is_equipment(self) -> bool:
        """装备 = 头盔/护甲/武器（有单件加成或套装加成）；装扮 = 纯时装外观（两者皆无）。"""
        return bool(self.bonus or self.suit_bonus)

    def as_dict(self) -> dict:
        return {
            "slot": self.slot,
            "id": self.id,
            "name": self.name,
            "bonus": self.bonus,
            "suit": self.suit,
            "suit_bonus": self.suit_bonus,
        }


@dataclass(slots=True)
class InventorySnapshot:
    """一次「背包/穿戴」快照的总结构。

    字段区分（务必分清，避免把装扮误判成装备）：
      - equipment：真正提供属性加成的装备（有 bonus/suit_bonus）
      - clothes  ：纯外观装扮（无加成）这里屏蔽掉了 避免对大模型造成干扰
      - items    ：道具
      - titles   ：称号
    """
    equipment: list[EquipEntry] = field(default_factory=list)   # 装备：有属性加成的部位
    #clothes: list[EquipEntry] = field(default_factory=list)     # 装扮：已停用，恒空（保留字段以兼容旧调用）
    items: list[InventoryItem] = field(default_factory=list)    # 道具
    titles: list[TitleEntry] = field(default_factory=list)      # 称号
    source: str = ""        # 数据来源："live:<uid>" / 抓包文件路径 / "1001"
    uid: int | None = None  # 账号 uid

    def as_dict(self) -> dict:
        return {
            "uid": self.uid,
            "source": self.source,
            "equipment": [e.as_dict() for e in self.equipment],
            # "clothes": [e.as_dict() for e in self.clothes],  # 装扮段已停用，不再输出
            "items": [{"id": i.id, "name": i.name, "count": i.count} for i in self.items],
            "titles": [t.as_dict() for t in self.titles],
        }


def _u32s(body: bytes) -> list[int]:
    if len(body) < 4:
        return []
    count = struct.unpack(">I", body[:4])[0]
    out = []
    for off in range(4, min(len(body), 4 + count * 4), 4):
        out.append(struct.unpack(">I", body[off:off + 4])[0])
    return out


def parse_frames_jsonl(path: str | Path) -> InventorySnapshot:
    """从 scan_frames 产物 jsonl（direction/cmd/body）解析。"""
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    snap = InventorySnapshot(source=str(path))
    for r in rows:
        cmd = r.get("cmd")
        body = bytes.fromhex(r.get("body", ""))
        if cmd == 2604:  # CHANGE_CLOTH：换「装备」（头盔/护甲/武器/目镜），count + 5 个 equip ID
            ids = _u32s(body)
            for obj_id in ids:
                snap.equipment.append(EquipEntry(slot="", id=obj_id))
        elif cmd == 42399:  # MULTI_ITEM_LIST：count + item IDs
            for obj_id in _u32s(body):
                snap.items.append(InventoryItem(id=obj_id))
        elif cmd == 3404 and len(body) >= 4:  # SETTITLE：单个 u32 title id
            tid = struct.unpack(">I", body[:4])[0]
            if tid:
                snap.titles.append(TitleEntry(id=tid))
    return snap


def _worn_sections(body: bytes) -> tuple[list[int], list[int]]:
    """从 1001 快照里取出两段 5 部位穿戴。

实测 Unity 1001 结构：
  - 装扮段：body 前部，5 个连续 equip ID（4 字节对齐）。
  - 装备段：body 后部，`[count][id 0][id 0]...`，每个装备 8 字节（id + 0）。

返回 (clothes_ids, equip_ids)。
"""
    if not body or len(body) < 24:
        return [], []

    # 装扮段已停用：不再解析，避免装扮数据污染「装备」判断。clothes 恒为空。
    clothes: list[int] = []
    # for off in range(0, max(0, len(body) - 20) + 1, 4):
    #     run = []
    #     p = off
    #     for _ in range(5):
    #         if p + 4 > len(body):
    #             break
    #         v = struct.unpack(">I", body[p:p + 4])[0]
    #         if not (0x130001 <= v <= 0x13FFFF):
    #             break
    #         run.append(v)
    #         p += 4
    #     if len(run) == 5:
    #         clothes = run
    #         break

    # 装备：[count][id 0] * count
    equip: list[int] = []
    for off in range(0, len(body) - 12):
        cnt = struct.unpack(">I", body[off:off + 4])[0]
        if not (4 <= cnt <= 12):
            continue
        ids: list[int] = []
        p = off + 4
        ok = True
        for _ in range(cnt):
            if p + 8 > len(body):
                ok = False
                break
            iid = struct.unpack(">I", body[p:p + 4])[0]
            zero = struct.unpack(">I", body[p + 4:p + 8])[0]
            if not (0x130001 <= iid <= 0x13FFFF) or zero != 0:
                ok = False
                break
            ids.append(iid)
            p += 8
        if ok:
            equip = ids
            break

    return clothes, equip


def _worn_title(body: bytes) -> int | None:
    """从 1001 快照提取当前称号 id。

    旧实现硬编码读 0x1396，已随登录快照结构变化失效（实测 1001 body 仅 ~4KB，
    称号 591 实际在 0x98c 附近）。改为扫描第一个「连续 3 个相同、值 ∈ 1..5000」
    的三连（实测称号/穿戴项区是 591/228/315/336 这类三连），best-effort。
    """
    if not body or len(body) < 12:
        return None
    for off in range(0, len(body) - 12, 4):
        v = struct.unpack_from(">I", body, off)[0]
        if not (1 <= v <= 5000):
            continue
        if (struct.unpack_from(">I", body, off + 4)[0] == v
                and struct.unpack_from(">I", body, off + 8)[0] == v):
            return v
    return None


def parse_equipment_from_1001(body: bytes | None) -> list[int]:
    """兼容旧接口：返回「装备」段 ID。"""
    return _worn_sections(body or b"")[1]


def parse_clothes_from_1001(body: bytes | None) -> list[int]:
    """已停用：装扮段不再解析，恒返回空。"""
    return []
    # return _worn_sections(body or b"")[0]


def _fill_entry(e: EquipEntry, provider: Any) -> EquipEntry:
    """补全装备/装扮条目的名称、部位、单件加成、套装（不改变它属于装备还是装扮）。"""
    d = provider.get("equip", e.id)
    if not d:
        return e
    e.name = d.get("name") or e.name
    pt = d.get("part_type") or {}
    if isinstance(pt, dict):
        e.slot = EQUIP_TYPE_NAMES.get(int(pt.get("id") or 0), e.slot)
    bonus = d.get("bonus")
    if isinstance(bonus, dict) and bonus.get("desc"):
        e.bonus = bonus["desc"]
    suit_ref = d.get("suit")
    suit_id = None
    if isinstance(suit_ref, dict) and suit_ref.get("id"):
        suit_id = int(suit_ref["id"])
    else:
        suit_id = _local_suit_map().get(int(e.id))
    if suit_id:
        sd = provider.get("suit", suit_id)
        if isinstance(sd, dict):
            e.suit = sd.get("name") or e.suit
            sb = sd.get("bonus") or {}
            if isinstance(sb, dict) and sb.get("desc"):
                e.suit_bonus = sb["desc"]
    return e


def resolve(snapshot: InventorySnapshot, provider: Any | None) -> InventorySnapshot:
    """用 SeerAPI 补全名称/部位/加成，保持「装备段 vs 装扮段」的归属不变。"""
    if provider is None:
        return snapshot

    # 1) 装备段补字段（装扮段已停用，不再补）
    snapshot.equipment = [_fill_entry(e, provider) for e in snapshot.equipment]
    # snapshot.clothes = [_fill_entry(e, provider) for e in snapshot.clothes]

    # 2) 道具反查
    for it in snapshot.items:
        name = provider.resolve("item", it.id)
        if name:
            it.name = name
        else:
            name2 = provider.resolve("factor", it.id)
            if name2:
                it.name = name2

    # 3) 称号反查（title.ability_desc / attr_bonus）
    for t in snapshot.titles:
        d = provider.get("title", t.id)
        if isinstance(d, dict):
            t.name = d.get("name") or t.name
            t.desc = d.get("desc") or ""
            t.bonus = d.get("ability_desc") or ""
            if not t.bonus:
                ab = d.get("attr_bonus") or {}
                if isinstance(ab, dict):
                    parts = []
                    for k, cn in (("hp", "体力"), ("atk", "攻击"), ("sp_atk", "特攻"),
                                  ("def_", "防御"), ("sp_def", "特防"), ("spd", "速度")):
                        v = ab.get(k)
                        if v:
                            parts.append(f"{cn}+{v}")
                    t.bonus = "，".join(parts)
    return snapshot


# ---------------------------------------------------------------------------
async def collect_raw(
    session: LoginSession,
    *,
    out_path: str | Path,
    settle: float = 2.0,
    keep: float = 3.0,
) -> list[dict]:
    c = GameClient(session, mode="unity")
    first = await c.connect(timeout=20.0)
    collected: list[dict] = []

    def add(f: Frame) -> None:
        collected.append({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body.hex()})

    if first is not None:
        add(first)

    loop = asyncio.get_running_loop()
    end = loop.time() + settle
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        add(f)

    for cmd in READ_CMDS:
        try:
            await c.send(cmd, [])
        except (ConnectionError, asyncio.IncompleteReadError):
            break
        end = loop.time() + keep
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            add(f)
    await c.close()

    if out_path:
        Path(out_path).write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in collected) + "\n", encoding="utf-8")
    return collected


def collect_from_credentials(account: str, password: str, out_path: str | Path) -> list[dict]:
    sess = authenticate_cached(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    return asyncio.run(collect_raw(sess, out_path=out_path))


def snapshot_from_1001(body: bytes, provider=None) -> InventorySnapshot:
    """直接从一个 1001 登录快照 body 解析穿戴装备/装扮/称号（可选 seerapi 反查名称）。"""
    snap = InventorySnapshot(source="1001")
    cloth_ids, equip_ids = _worn_sections(body)
    for obj_id in equip_ids:
        snap.equipment.append(EquipEntry(slot="", id=obj_id))
    # 装扮段已停用：不再写入 snapshot.clothes
    # for obj_id in cloth_ids:
    #     snap.clothes.append(EquipEntry(slot="", id=obj_id))
    tid = _worn_title(body)
    if tid:
        snap.titles.append(TitleEntry(id=tid))
    if provider is not None:
        return resolve(snap, provider)
    return snap


def snapshot_from_live(account: str, password: str, out_path: str | Path | None) -> InventorySnapshot:
    rows = collect_from_credentials(account, password, out_path) if out_path else _collect_mem(account, password)
    snap = InventorySnapshot(source=f"live:{account}")
    body = None
    for r in rows:
        if r["cmd"] == 1001:
            body = bytes.fromhex(r["body"])
            break
    if body:
        cloth_ids, equip_ids = _worn_sections(body)
        for obj_id in equip_ids:
            snap.equipment.append(EquipEntry(slot="", id=obj_id))
        # 装扮段已停用：不再写入 snapshot.clothes
        # for obj_id in cloth_ids:
        #     snap.clothes.append(EquipEntry(slot="", id=obj_id))
        tid = _worn_title(body)
        if tid:
            snap.titles.append(TitleEntry(id=tid))
    return snap


def read_equipment(account: str, password: str, *, resolve_names: bool = True) -> dict:
    """只读实战关心的「装备 + 称号」（不含装扮、不含道具）。

    实战中影响作战能力的核心就是这两项：
      - equipment：有属性加成的装备部位
      - titles   ：称号（提供称号加成）

    返回：{"equipment": [...], "titles": [...]}
    """
    from .provider import SeerApiProvider

    snap = snapshot_from_live(account, password, None)
    if resolve_names:
        snap = resolve(snap, SeerApiProvider())
    return {
        "equipment": [e.as_dict() for e in snap.equipment],
        "titles": [t.as_dict() for t in snap.titles],
    }


async def _collect_items_async(account: str, password: str) -> list[dict]:
    """登录后只发 42399(MULTI_ITEM_LIST) 收集道具背包帧。"""
    sess = authenticate_cached(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)  # 1001 握手被消费，忽略
    collected: list[dict] = []
    try:
        await c.send(42399, [])
    except (ConnectionError, asyncio.IncompleteReadError):
        await c.close()
        return collected
    end = asyncio.get_running_loop().time() + 4.0
    while asyncio.get_running_loop().time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - asyncio.get_running_loop().time()))
        except asyncio.TimeoutError:
            continue
        collected.append({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body.hex()})
    await c.close()
    return collected


def read_items(account: str, password: str, *, resolve_names: bool = True) -> dict:
    """只读背包道具（42399 MULTI_ITEM_LIST），返回：{"items": [{"id","name","count"}, ...]}。"""
    from .provider import SeerApiProvider

    rows = asyncio.run(_collect_items_async(account, password))
    items: list[InventoryItem] = []
    for r in rows:
        if r["cmd"] == 42399:
            for iid in _u32s(bytes.fromhex(r["body"])):
                if iid:
                    items.append(InventoryItem(id=iid))
    if resolve_names and items:
        prov = SeerApiProvider()
        for it in items:
            it.name = prov.resolve("item", it.id) or ""
    return {"items": [{"id": i.id, "name": i.name, "count": i.count} for i in items]}


_AUTH_CACHE: dict[str, tuple[float, LoginSession]] = {}


def _collect_mem(account: str, password: str) -> list[dict]:
    return asyncio.run(_collect_mem_async(account, password))


async def _collect_mem_async(account: str, password: str) -> list[dict]:
    import tempfile
    sess = authenticate_cached(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    first = await c.connect(timeout=20.0)
    collected: list[dict] = []
    # 登录快照(1001)在 connect() 握手阶段已被消费，这里作为返回值补齐，
    # 否则装备/装扮/称号永远读不到。
    if first is not None:
        collected.append({"cmd": first.cmd, "result": first.result, "len": len(first.body), "body": first.body.hex()})
    end = asyncio.get_running_loop().time() + 4.0
    while asyncio.get_running_loop().time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - asyncio.get_running_loop().time()))
        except asyncio.TimeoutError:
            continue
        collected.append({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body.hex()})
    await c.close()
    return collected