"""查 3 只候选超能宠当前实际装备的 5 个技能槽（2301，先读 43706 加载背包）。"""
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

CANDIDATES = [
    (3567, 0x640CB1EA),
    (3465, 0x60328EC1),
    (3507, 0x64652638),
]


def skname(sid):
    m = DATA.moves.get(sid)
    return m.name if m else str(sid)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    await c.send(43706, [])  # 先加载背包
    await asyncio.sleep(1.5)
    for species, ct in CANDIDATES:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])

    results = {}
    loop = asyncio.get_running_loop()
    end = loop.time() + 12.0
    while loop.time() < end and len(results) < len(CANDIDATES):
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2301 and len(f.body) >= 4:
            sp = struct.unpack_from(">I", f.body, 0)[0]
            d = parse_2301(f.body)
            results[sp] = d
    await c.close()

    print("=== 候选超能宠 实际装备技能 ===")
    for species, ct in CANDIDATES:
        d = results.get(species)
        if d:
            skills = d.skills
            print(f"{species} species={species} catch={hex(ct)} lv={d.level} HP={d.max_hp}")
            print(f"    装备技能: " + ", ".join(f"{sid}({skname(sid)})" for sid in skills))
        else:
            print(f"{species} catch={hex(ct)} -> 仍无回包")


asyncio.run(main())