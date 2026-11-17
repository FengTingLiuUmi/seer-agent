"""查 84公式 三件套的装备技能与等级 + 当前正式栏位。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pet_details import parse_2301
from seer_rebuild.battle_data import BattleData
from seer_rebuild.pets import parse_bag_43706

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
DATA = BattleData(r"F:\seer\seer_cfg\json")

# 84: 帝皇之御(3512) 守御八方31505 / 六界神王(3045) 剑挥四方19314 / 时空界皇(3463) 补刀
CHECK = [(3512, 0x602211AE), (3045, 0x62EF6F18), (3463, 0x5FFD1DD6)]


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

    bag = b""
    results = {}
    loop = asyncio.get_running_loop()
    end = loop.time() + 12.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706 and not bag:
            bag = f.body
        elif f.cmd == 2301 and len(f.body) >= 4:
            sp = struct.unpack_from(">I", f.body, 0)[0]
            results[sp] = parse_2301(f.body)
    await c.close()

    cnt, pets = parse_bag_43706(bag, data=DATA) if bag else (0, [])
    print("=== 当前 43706（正式前 cnt 只）===", "head=", struct.unpack_from(">I", bag, 0)[0] if bag else None)
    for i, pt in enumerate(pets):
        sp = DATA.species.get(pt.species_id)
        name = sp.name if sp else str(pt.species_id)
        tag = "正式" if i < (struct.unpack_from(">I", bag, 0)[0] if bag else 0) else "待命"
        print(f"  [{tag}] {name} sp={pt.species_id} catch={hex(pt.catch_time)}")

    print("\n=== 84三件套 2301 ===")
    for species, ct in CHECK:
        d = results.get(species)
        if d:
            print(f"{species} catch={hex(ct)} lv={d.level} 技能: " + ", ".join(f"{sid}({skname(sid)})" for sid in d.skills))
        else:
            print(f"{species} catch={hex(ct)} -> 无")


asyncio.run(main())