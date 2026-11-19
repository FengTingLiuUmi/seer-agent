"""精英仓库（精英收藏，2361）→ 背包（43706）的移动能力。

协议（jybbrb.pcapng 账号 ACCOUNT 实证）：

  - 读精英仓库：`2361 GET_LOVE_PET_LIST`（C2S 空 body）→ S2C `[count] + N×[species,flag,catch_time]`
  - 加入背包：`2304 PET_RELEASE` body = `[catch_time][flag]`
      flag 1 = 加入正式（主队背包）
      flag 2 = 加入待命（背包待命区）
      flag 0 = 正式放回仓库 / flag 3 = 待命放回仓库 / flag 4 = 正式降待命

catch_time 是精灵个体唯一标识（同一 species 可有多只，靠 catch_time 区分）。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .commands import Cmd
from .connection import open_unity
from .pets import parse_pet_list, release_body

SLOT_FLAG = {"formal": 1, "reserve": 2}
SLOT_NAME = {1: "正式", 2: "待命"}


@dataclass(slots=True)
class ElitePet:
    species_id: int
    flag: int
    catch_time: int
    name: str = ""


def _resolve_names(entries: list[ElitePet], *, provider=None) -> list[ElitePet]:
    """用本地 monsters_pro.ini（快）优先，再退回 seerapi。"""
    if not entries:
        return entries
    data = None
    try:
        from .battle_data import BattleData
        data = BattleData(r"F:\seer\seer_cfg\json")
    except Exception:
        data = None
    for e in entries:
        name = ""
        if data is not None:
            sp = data.species.get(e.species_id)
            name = sp.name if sp else ""
        if not name and provider is not None:
            name = provider.resolve("pet", e.species_id) or ""
        e.name = name or str(e.species_id)
    return entries


async def _read_elite_async(account: str, password: str, *, resolve_names: bool = True) -> dict:
    c = await open_unity(account, password)
    uid = c.session.uid

    # 读精英仓库
    await c.send(Cmd.GET_LOVE_PET_LIST, [])

    loop = asyncio.get_running_loop()
    body = b""
    end = loop.time() + 10.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == Cmd.GET_LOVE_PET_LIST and len(f.body) >= 4:
            body = f.body
            break

    entries = [ElitePet(e.species_id, e.flag, e.catch_time) for e in parse_pet_list(body)]
    if resolve_names:
        _resolve_names(entries)
    await c.close()

    return {
        "uid": uid,
        "count": len(entries),
        "pets": [{"species_id": e.species_id, "name": e.name, "flag": e.flag, "catch_time": e.catch_time} for e in entries],
    }


def read_elite_warehouse(account: str, password: str, *, resolve_names: bool = True) -> dict:
    """在线读精英仓库（2361），返回 species/flag/catch_time 列表。只读。"""
    return asyncio.run(_read_elite_async(account, password, resolve_names=resolve_names))


def _find_catch(entries: list[ElitePet], species_id: int) -> list[ElitePet]:
    return [e for e in entries if e.species_id == species_id]


def plan_add(catch_time: int, *, slot: str = "formal") -> dict:
    """构造「精英仓库 → 背包」的 2304 移动步骤（不登录）。"""
    flag = SLOT_FLAG[slot]
    body = release_body(catch_time, flag)
    return {
        "cmd": Cmd.PET_RELEASE,
        "slot": SLOT_NAME[flag],
        "flag": flag,
        "catch_time": catch_time,
        "body_hex": body.hex(),
        "write": True,
    }


def add_to_bag(
    account: str,
    password: str,
    *,
    catch_time: int | None = None,
    species_id: int | None = None,
    slot: str = "formal",
    send: bool = False,
    resolve_names: bool = True,
) -> dict:
    """从精英仓库把精灵加入背包（默认 dry-run 只读+规划，不发写包）。

    - ``catch_time``：直接指定个体。
    - ``species_id``：按 species 在精英仓库里找个体（找到多只时取第一只 flag==0 的，
      即尚未出战的）；找不到则报错。
    - ``slot``：formal=加入正式(flag=1) / reserve=加入待命(flag=2)。
    - ``send``：True 才真正发包（写操作）。
    """
    if slot not in SLOT_FLAG:
        raise ValueError(f"slot 必须是 formal/reserve，得到 {slot!r}")

    # 1) 定位 catch_time
    if catch_time is None:
        if species_id is None:
            raise ValueError("需要 catch_time 或 species_id 之一")
        elite = read_elite_warehouse(account, password, resolve_names=resolve_names)
        entries = [ElitePet(p["species_id"], p["flag"], p["catch_time"], p.get("name", "")) for p in elite["pets"]]
        hits = _find_catch(entries, species_id)
        if not hits:
            raise SystemExit(f"精英仓库里没有 species={species_id} 的精灵（先 `warehouse list` 看清单）")
        # 优先选未出战(flag==0)的个体
        pick = next((e for e in hits if e.flag == 0), hits[0])
        catch_time = pick.catch_time
        matched_name = pick.name or str(species_id)
    else:
        matched_name = str(catch_time)

    plan = plan_add(catch_time, slot=slot)
    plan["species_id"] = species_id
    plan["name"] = matched_name

    if not send:
        plan["dry_run"] = True
        return plan

    # 2) 真发包
    out: dict = dict(plan, dry_run=False, recv=[])

    async def _send() -> None:
        c = await open_unity(account, password)
        out["uid"] = c.session.uid
        await c.send(Cmd.PET_RELEASE, [bytes.fromhex(plan["body_hex"])])
        loop = asyncio.get_running_loop()
        end = loop.time() + 3.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            out["recv"].append({"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body[:32].hex()})
            if f.cmd == Cmd.PET_RELEASE:
                break
        await c.close()

    asyncio.run(_send())
    return out