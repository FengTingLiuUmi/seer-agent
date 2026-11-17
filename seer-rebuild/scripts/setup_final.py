"""最终配队：卫岳首发 + 西游四件套 + 启灵元神（神照给首发护盾）。"""
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

KEEP = {  # 西游四 + 卫岳首发 + 启灵元神
    2727: 0x600B3F8C,  # 蒙奇多克
    3409: 0x600B3F89,  # 三藏
    3519: 0x600B3F86,  # 沙悟净
    2735: 0x600B4033,  # 天河神将
    3986: 0x60C30355,  # 启灵元神
    4510: 0x648604F2,  # 卫岳（首发）
}
STARTER = 0x648604F2  # 卫岳


def nm(s):
    sp = DATA.species.get(s)
    return sp.name if sp else str(s)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

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
    formal = pets[:struct.unpack_from(">I", bag, 0)[0]]
    print("当前正式:", [(nm(p.species_id), hex(p.catch_time)) for p in formal])

    keep_ct = set(KEEP.values())
    # 移除不需要的
    for p in formal:
        if p.catch_time not in keep_ct:
            await c.send(2304, [struct.pack(">I", p.catch_time), struct.pack(">I", 0)])
            await asyncio.sleep(0.6)
            print(f"  移除 {nm(p.species_id)} {hex(p.catch_time)}")

    # 加入缺的
    formal_ct = {p.catch_time for p in formal}
    for sp, ct in KEEP.items():
        if ct not in formal_ct:
            await c.send(2304, [struct.pack(">I", ct), struct.pack(">I", 1)])
            await asyncio.sleep(0.6)
            print(f"  加入 {nm(sp)} {hex(ct)}")

    # 卫岳首发
    await c.send(2308, [struct.pack(">I", STARTER)])
    await asyncio.sleep(0.6)
    await c.close()
    print("完成：卫岳首发 + 西游4 + 启灵元神")


asyncio.run(main())