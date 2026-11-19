import asyncio, struct, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.connection import open_unity
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData

REMOVE = [0x62af4fd3, 0x602fe200, 0x60312cb4]           # 蒂朵/六界帝神/月照(第2关已锁)
ADD    = [1472551551]                                     # 圣灵谱尼(仓库)
STARTER = 1472551551
# 漆黑天使套4件(头/腰/手/足，不含目镜) + 神话称号300
EQUIP_IDS = [1301043, 1301045, 1301044, 1301046]
TITLE_ID = 300

def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)

async def drain(c, t=1.5):
    loop = asyncio.get_running_loop()
    end = loop.time() + t
    got = []
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        got.append(f)
    return got

async def main(acct, pw):
    bd = BattleData(r"F:\seer\seer_cfg\json")
    c = await open_unity(acct, pw)
    out = []
    for ct in REMOVE:
        await c.send(2304, [u32(ct) + u32(0)])
        await drain(c)
        out.append(f"remove 0x{ct:08x}")
    for ct in ADD:
        await c.send(2304, [u32(ct) + u32(1)])
        await drain(c)
        out.append(f"add formal 0x{ct:08x}")
    await c.send(2308, [u32(STARTER)])
    await drain(c)
    out.append(f"starter 0x{STARTER:08x}")
    # 换装备(4件) + 称号
    body = u32(len(EQUIP_IDS)) + b"".join(u32(i) for i in EQUIP_IDS)
    await c.send(2604, [body])
    await drain(c, 2.0)
    out.append(f"equip {EQUIP_IDS}")
    await c.send(3404, [u32(TITLE_ID)])
    await drain(c, 2.0)
    out.append(f"title {TITLE_ID}")
    # 读背包验证
    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 5.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706:
            cnt, pets = parse_bag_43706(f.body, data=bd)
            fm = pets[:cnt]
            names = [f"{bd.species.get(p.species_id).name if bd.species.get(p.species_id) else p.species_id}(0x{p.catch_time:08x})" for p in fm]
            out.append(f"FORMAL={cnt}: " + ", ".join(names))
            break
    await c.close()
    print("\n".join(out))

asyncio.run(main(sys.argv[1], sys.argv[2]))