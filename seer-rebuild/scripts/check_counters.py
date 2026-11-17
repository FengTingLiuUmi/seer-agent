"""只读查候选超能宠的等级 + 当前 5 个技能槽（2301）。"""
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

# 候选超能宠 (species, catch) — 精英仓库里找到的
CANDIDATES = [
    (3567, 0x640CB1EA, "魔钰(超能)"),
    (3465, 0x60328EC1, "圣瞳缪斯(圣灵超能)"),
    (3507, 0x64652638, "冥王·苍月影(超能冰)"),
    (4329, 0x66802C4D, "倪克斯(神秘超能)"),
    (4208, 0x625F809A, "锢灵·舞(混沌超能)"),
    (3667, 0x62A4D551, "混沌天蛇太祖(混沌超能)"),
    (4510, 0x648604F2, "卫岳(水超能)"),
]


def name_of(species):
    sp = DATA.species.get(species)
    return sp.name if sp else str(species)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    for species, ct, label in CANDIDATES:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])
    await c.send(104857, [])  # 无效缓冲命令也不影响

    results = {}
    loop = asyncio.get_running_loop()
    end = loop.time() + 8.0
    while loop.time() < end and len(results) < len(CANDIDATES):
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2301 and len(f.body) >= 4:
            species = struct.unpack_from(">I", f.body, 0)[0]
            d = parse_2301(f.body)
            results[species] = d
    await c.close()

    print("=== 候选超能宠 等级/能力值/技能 ===")
    for species, ct, label in CANDIDATES:
        d = results.get(species)
        if d:
            sn = [s for s in DATA.moves if DATA.moves[s].name and False]
            skills = ", ".join(f"{sid}({DATA.moves.get(sid).name if sid in DATA.moves else '?'})" for sid in d.skills)
            print(f"{species} {label} catch={hex(ct)} 物种={name_of(species)} lv={d.level} HP={d.max_hp} 攻={d.atk} 特攻={d.sp_atk} 速={d.spd}")
            print(f"     技能槽: {skills}")
        else:
            print(f"{species} {label} catch={hex(ct)}  -> 2301 无回包")


asyncio.run(main())