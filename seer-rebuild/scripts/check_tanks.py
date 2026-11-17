"""查圣灵谱尼(5000)/王之哈莫(3022)/弑序神罗(4169) 的 HP + 技能 + 魂印（找锁伤/减伤/回血/百分比）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pet_details import parse_2301
from seer_rebuild.battle_data import BattleData

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
DATA = BattleData(r"F:\seer\seer_cfg\json")
p = SeerApiProvider()

CHECK = [(5000, 0x57C55A7F), (3022, 0x57B67917), (4169, 0x5FF913DE)]


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    await c.send(43706, [])
    await asyncio.sleep(1.0)
    for species, ct in CHECK:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])
    results = {}
    loop = asyncio.get_running_loop()
    end = loop.time() + 10.0
    while loop.time() < end and len(results) < len(CHECK):
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2301 and len(f.body) >= 4:
            sp = struct.unpack_from(">I", f.body, 0)[0]
            results[sp] = parse_2301(f.body)
    await c.close()

    for species, ct in CHECK:
        d = results.get(species)
        if not d:
            print(f"{species} catch={hex(ct)} -> 无")
            continue
        pet = p.get("pet", species, fields=["id", "name", "type", "soulmark"])
        smk = []
        for sm in (pet.get("soulmark") or []):
            smd = p.get("soulmark", sm["id"]) if sm.get("id") else None
            smk.append((smd or {}).get("desc") or str(sm.get("id")))
        print(f"\n{species} {pet.get('name')} [{combo((pet.get('type') or {}).get('id'))}] lv={d.level} HP={d.max_hp} 物攻={d.atk} 特攻={d.sp_atk} 防={d.def_} 速={d.spd}")
        print("  魂印:", smk)
        for sid in d.skills:
            m = DATA.moves.get(sid)
            print(f"    技能 {sid} {m.name if m else '?'} power={m.power if m else '?'} type={m.type if m else '?'}")


asyncio.run(main())