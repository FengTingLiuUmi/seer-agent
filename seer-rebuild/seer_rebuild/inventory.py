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
    id: int
    name: str = ""
    count: int = 1

    @property
    def label(self) -> str:
        return self.name or f"[{self.id}]"


@dataclass(slots=True)
class TitleEntry:
    id: int
    name: str = ""
    bonus: str = ""
    desc: str = ""

    @property
    def label(self) -> str:
        return self.name or f"[{self.id}]"

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "bonus": self.bonus, "desc": self.desc}


@dataclass(slots=True)
class EquipEntry:
    slot: str
    id: int
    name: str = ""
    bonus: str = ""
    suit: str = ""
    suit_bonus: str = ""

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
    """equipment=有属性的装备；clothes=纯外观装扮；items=道具；titles=称号。"""
    equipment: list[EquipEntry] = field(default_factory=list)
    clothes: list[EquipEntry] = field(default_factory=list)
    items: list[InventoryItem] = field(default_factory=list)
    titles: list[TitleEntry] = field(default_factory=list)
    source: str = ""
    uid: int | None = None

    def as_dict(self) -> dict:
        return {
            "uid": self.uid,
            "source": self.source,
            "equipment": [e.as_dict() for e in self.equipment],
            "clothes": [e.as_dict() for e in self.clothes],
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

    # 装扮：第一个「连续 5 个 0x13xxxx」run（间隔 4）
    clothes: list[int] = []
    for off in range(0, max(0, len(body) - 20) + 1, 4):
        run = []
        p = off
        for _ in range(5):
            if p + 4 > len(body):
                break
            v = struct.unpack(">I", body[p:p + 4])[0]
            if not (0x130001 <= v <= 0x13FFFF):
                break
            run.append(v)
            p += 4
        if len(run) == 5:
            clothes = run
            break

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
    """从 1001 快照提取当前称号 id（实测：装备段前 0x1396 的 4 字节 BE 低位即称号 id）。"""
    if not body or len(body) < 0x139c:
        return None
    v4 = struct.unpack_from(">I", body, 0x1396)[0]
    if 1 <= v4 <= 5000:
        return v4
    v2 = struct.unpack_from(">H", body, 0x1398)[0]
    return v2 if 1 <= v2 <= 5000 else None


def parse_equipment_from_1001(body: bytes | None) -> list[int]:
    """兼容旧接口：返回「装备」段 ID。"""
    return _worn_sections(body or b"")[1]


def parse_clothes_from_1001(body: bytes | None) -> list[int]:
    """返回「装扮」段 ID。"""
    return _worn_sections(body or b"")[0]


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

    # 1) 装备段与装扮段分别补字段，不再按 bonus 重新分流
    snapshot.equipment = [_fill_entry(e, provider) for e in snapshot.equipment]
    snapshot.clothes = [_fill_entry(e, provider) for e in snapshot.clothes]

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
    for obj_id in cloth_ids:
        snap.clothes.append(EquipEntry(slot="", id=obj_id))
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
        for obj_id in cloth_ids:
            snap.clothes.append(EquipEntry(slot="", id=obj_id))
        tid = _worn_title(body)
        if tid:
            snap.titles.append(TitleEntry(id=tid))
    return snap


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