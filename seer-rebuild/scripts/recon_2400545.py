"""一次性只读探测：读完「戟决先锋 2400545」进度 + 当前背包(正式/待命 catch_time) + 精英仓库。"""
import asyncio
import struct
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pets import parse_pet_list
from seer_rebuild.factor_runner import parse_forever

ACCOUNT = "ACCOUNT"
PASSWORD = "PASSWORD"

# 戟决先锋因子 2400545 的 forever 键
FACTOR_2400545 = dict(progress=302210, time=302211, fail=302208)
GET_MULTI_FOREVER = 46046
BAG = 43706
ELITE = 2361

from seer_rebuild.battle_data import BattleData
DATA = BattleData(r"F:\seer\seer_cfg\json")


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0] if len(b) >= o + 4 else 0


def name_of(species):
    sp = DATA.species.get(species)
    return sp.name if sp else str(species)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    await c.send(GET_MULTI_FOREVER, [struct.pack(">I", 3) + b"".join(struct.pack(">I", k) for k in FACTOR_2400545.values())])
    await c.send(BAG, [])
    await c.send(ELITE, [])

    forever = None
    bag_body = None
    elite_body = None
    loop = asyncio.get_running_loop()
    end = loop.time() + 10.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == GET_MULTI_FOREVER and forever is None and len(f.body) >= 4:
            forever = parse_forever(f.body)
        elif f.cmd == BAG and bag_body is None:
            bag_body = f.body
        elif f.cmd == ELITE and elite_body is None:
            elite_body = f.body
        if forever is not None and bag_body is not None and elite_body is not None:
            break
    await c.close()

    print("=== 戟决先锋 2400545 进度 (46046 keys progress/time/fail) ===")
    print("  forever values =", forever, " -> progress(第0关/0基?) =", forever[0] if forever else None)

    print("\n=== 当前背包 43706 ===")
    if bag_body:
        print(f"  body len={len(bag_body)}  head_u32={[hex(u32(bag_body, k)) for k in range(0, 24, 4)]}")
        # 用 pets.parse_bag_43706 识别 species+catch
        from seer_rebuild.pets import parse_bag_43706
        cnt, pets = parse_bag_43706(bag_body, data=DATA)
        print(f"  count头={u32(bag_body,0)} 识别到 {len(pets)} 只：")
        for p in pets:
            print(f"    {name_of(p.species_id)} species={p.species_id} catch={p.catch_time:#x}")

    print("\n=== 精英仓库 2361 ===")
    if elite_body:
        pets = parse_pet_list(elite_body)
        print(f"  count={len(pets)}")
        # 只打印关键的几只：3670 黄金天马 / 3512 帝皇之御 / 5000 圣灵谱尼 / 2977 / 3463 / 3022
        keys = set()
        for e in pets:
            if e.species_id in (3670, 3512, 5000, 2977, 3463, 3022, 3045, 3194, 4169):
                print(f"    {name_of(e.species_id)} species={e.species_id} flag={e.flag} catch={e.catch_time:#x}")
            keys.add(e.catch_time)
    print("\nDONE")


asyncio.run(main())