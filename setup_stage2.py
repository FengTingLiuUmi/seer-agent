import asyncio, struct, sys, json
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.connection import open_unity
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData

# 第2关阵容（普通难度，design 266）：蒂朵 → 六界帝神 → 月照星魂
REMOVE = [1612845486, 1659858712, 1610423766, 1795108500, 1780054592]  # 帝皇/六界神王/时空/霞冠/希瓦(第1关已锁)
ADD = [1655656403, 1613750784, 1613835444]  # 蒂朵, 六界帝神, 月照星魂
STARTER = 1655656403

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
        await c.send(2304, [u32(ct) + u32(0)])   # flag=0 正式放回仓库
        await drain(c)
        out.append(f"remove formal 0x{ct:08x}")
    for ct in ADD:
        await c.send(2304, [u32(ct) + u32(1)])   # flag=1 仓库->正式
        await drain(c)
        out.append(f"add formal 0x{ct:08x}")
    await c.send(2308, [u32(STARTER)])           # 设首发
    await drain(c)
    out.append(f"starter 0x{STARTER:08x}")

    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 5.0
    bag = None
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706:
            cnt, pets = parse_bag_43706(f.body, data=bd)
            bag = (cnt, pets)
            break
    if bag:
        cnt, pets = bag
        fm = pets[:cnt]
        names = [f"{bd.species.get(p.species_id).name if bd.species.get(p.species_id) else p.species_id}(0x{p.catch_time:08x})" for p in fm]
        out.append(f"FORMAL={cnt}: " + ", ".join(names))
        rs = pets[cnt:]
        rnames = [f"{bd.species.get(p.species_id).name if bd.species.get(p.species_id) else p.species_id}(0x{p.catch_time:08x})" for p in rs]
        if rnames:
            out.append("RESERVE: " + ", ".join(rnames))
    else:
        out.append("BAG_READ_FAILED")
    await c.close()
    print("\n".join(out))

asyncio.run(main(sys.argv[1], sys.argv[2]))