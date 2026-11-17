"""读普通仓库 2303，找西游四件套（天河神将/沙悟净等）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.battle_data import BattleData

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
DATA = BattleData(r"F:\seer\seer_cfg\json")


def nm(s):
    sp = DATA.species.get(s)
    return sp.name if sp else str(s)


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    await c.send(2303, [struct.pack(">I", 0), struct.pack(">I", 400)])
    loop = asyncio.get_running_loop()
    end = loop.time() + 8.0
    body = b""
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2303 and len(f.body) >= 4:
            body = f.body
            break
    await c.close()

    if not body:
        print("2303 无回包")
        return
    print("2303 raw len =", len(body), " head =", [hex(struct.unpack_from('>I', body, i)[0]) for i in range(0, min(24, len(body)), 4)])
    # 尝试 16B/项
    cnt = struct.unpack_from(">I", body, 0)[0]
    print("count头 =", cnt)
    # 前 N 只（先试 16B）
    for k in range(min(cnt, 400)):
        o = 4 + k * 16
        if o + 16 > len(body):
            break
        s, fl, ct, lv = struct.unpack_from(">IIII", body, o)
        if 1 <= s <= 6000:
            name = nm(s)
            print(f"  [{k}] {name} sp={s} flag={fl} catch={hex(ct)} lv={lv}")


asyncio.run(main())