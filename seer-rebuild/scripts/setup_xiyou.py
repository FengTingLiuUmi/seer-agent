"""配西游套阵容：正式放 4 西游 + 魔钰首发（触发首发全属性+1）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
DATA = BattleData(r"F:\seer\seer_cfg\json")

XIYOU = {
    3409: 0x600B3F89,  # 三藏
    2727: 0x600B3F8C,  # 蒙奇多克
    3519: 0x600B3F86,  # 沙悟净
    2735: 0x600B4033,  # 天河神将
}
STARTER = 0x640CB1EA  # 魔钰


def nm(s):
    sp = DATA.species.get(s)
    return sp.name if sp else str(s)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    # 1) 读当前正式
    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    bag = b""
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706 and len(f.body) >= 4:
            bag = f.body
            break
    cnt, pets = parse_bag_43706(bag, data=DATA)
    formal_head = struct.unpack_from(">I", bag, 0)[0]
    formal = pets[:formal_head]
    print("当前正式:", [(nm(p.species_id), hex(p.catch_time)) for p in formal])

    keep = set(XIYOU.values()) | {STARTER}
    # 2) 移除不需要的正式宠物
    for p in formal:
        if p.catch_time not in keep:
            await c.send(2304, [struct.pack(">I", p.catch_time), struct.pack(">I", 0)])  # flag=0 放回仓库
            await asyncio.sleep(0.6)
            print(f"  移除 {nm(p.species_id)} {hex(p.catch_time)}")

    # 3) 加入 4 西游（若不在正式）
    for sp, ct in XIYOU.items():
        if ct not in [p.catch_time for p in formal]:
            await c.send(2304, [struct.pack(">I", ct), struct.pack(">I", 1)])  # flag=1 加入正式
            await asyncio.sleep(0.6)
            print(f"  加入西游 {nm(sp)} {hex(ct)}")

    # 4) 魔钰首发
    await c.send(2308, [struct.pack(">I", STARTER)])
    await asyncio.sleep(0.6)
    print(f"  魔钰 {hex(STARTER)} 设首发")

    # 5) 验证
    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    bag = b""
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706 and len(f.body) >= 4:
            bag = f.body
            break
    cnt, pets = parse_bag_43706(bag, data=DATA)
    formal_head = struct.unpack_from(">I", bag, 0)[0]
    print("新正式:", [(nm(p.species_id), hex(p.catch_time)) for p in pets[:formal_head]])

    await c.close()


asyncio.run(main())