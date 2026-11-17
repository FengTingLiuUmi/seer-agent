"""查 弑序神罗(4169) / 倪克斯(4329) 的等级+装备技能（2301，先读43706）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pet_details import parse_2301
from seer_rebuild.battle_data import BattleData

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
DATA = BattleData(r"F:\seer\seer_cfg\json")
CAND = [(4169, 0x5FF913DE), (4329, 0x66802C4D), (4208, 0x625F809A)]


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
    await asyncio.sleep(1.2)
    for species, ct in CAND:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])

    results = {}
    loop = asyncio.get_running_loop()
    end = loop.time() + 12.0
    while loop.time() < end and len(results) < len(CAND):
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2301 and len(f.body) >= 4:
            sp = struct.unpack_from(">I", f.body, 0)[0]
            results[sp] = parse_2301(f.body)
    await c.close()

    for species, ct in CAND:
        d = results.get(species)
        if d:
            print(f"{species} catch={hex(ct)} lv={d.level} HP={d.max_hp} 特攻={d.sp_atk}")
            print("    装备:", ", ".join(f"{sid}({skname(sid)})" for sid in d.skills))
        else:
            print(f"{species} catch={hex(ct)} -> 无回包")


asyncio.run(main())