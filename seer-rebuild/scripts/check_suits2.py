"""只读：批量探测候选战斗套装是否已拥有（42399 只回已拥有件）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

SUITS = {
    "银翼365": [1300670, 1300671, 1300672, 1300673],
    "皇帝勇武377": [1300724, 1300725, 1300726, 1300727],
    "天尊400": [1300826, 1300827, 1300828, 1300829],
    "元神411": [1300875, 1300876, 1300877, 1300878],
    "飞翼419": [1300909, 1300910, 1300911, 1300912],
    "永夜421": [1300918, 1300919, 1300920, 1300921],
    "圣乐BOSS430": [1300959, 1300960, 1300961, 1300962],
    "苍星437": [1300989, 1300990, 1300991, 1300992, 1300993],
    "空元442": [1301015, 1301016, 1301017, 1301018],
    "漆黑之套448": [1301043, 1301044, 1301045, 1301046],
    "遗迹458": [1301083, 1301084, 1301085, 1301086],
    "黄金逆袭477": [1301158, 1301159, 1301160, 1301161],
    "帝皇战甲479": [1301167, 1301168, 1301169],
}


async def main() -> None:
    account, password = sys.argv[1], sys.argv[2]
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    id2suit = {}
    all_ids = []
    for name, ids in SUITS.items():
        for i in ids:
            id2suit[i] = name
            all_ids.append(i)

    body = struct.pack(">I", len(all_ids)) + b"".join(struct.pack(">I", i) for i in all_ids)
    await c.send(42399, [body])
    print(f"[sent] 42399 探测 {len(all_ids)} 件")
    owned = []
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 42399:
            b = f.body
            n = struct.unpack_from(">I", b, 0)[0]
            for k in range(n):
                off = 4 + k * 20
                if off + 20 > len(b):
                    break
                eid = struct.unpack_from(">I", b, off)[0]
                flag = struct.unpack_from(">I", b, off + 4)[0]
                owned.append((eid, flag))
            break
    print("已拥有件：", len(owned))
    suit_owned = {}
    for eid, flag in owned:
        sn = id2suit.get(eid, "?")
        suit_owned.setdefault(sn, 0)
        suit_owned[sn] += 1
    for name, ids in SUITS.items():
        c20 = suit_owned.get(name, 0)
        full = c20 >= len(ids)
        mark = "★完整拥有" if full else ("部分" if c20 else "无")
        print(f"  {name}: {c20}/{len(ids)} {mark}")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())