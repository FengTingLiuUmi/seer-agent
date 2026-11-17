"""查 卫岳(4510 水+超能) / 擎空凡尔斯(3697 纯飞行) / 魔钰复产 等级+装备技能+最强输出。"""
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

CHECK = [(4510, 0x648604F2), (3697, 0x60256A50), (3567, 0x640CB1EA)]


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


def skname(sid):
    m = DATA.moves.get(sid)
    return m.name if m else str(sid)


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
        comb = combo((p.get('pet', species, fields=['type']) or {}).get('type', {}).get('id'))
        print(f"{species} [{comb}] catch={hex(ct)} lv={d.level} HP={d.max_hp} 特攻={d.sp_atk} 物攻={d.atk}")
        for sid in d.skills:
            sd = p.get("skill", sid, fields=["id", "name", "power", "type", "priority"])
            st = (sd.get("type") or {}).get("id") if sd else None
            tn = combo(st) if st else "?"
            pw = (sd or {}).get("power")
            print(f"     {sid} {skname(sid)} power={pw} 类型={tn} 先制={(sd or {}).get('priority')}")


asyncio.run(main())