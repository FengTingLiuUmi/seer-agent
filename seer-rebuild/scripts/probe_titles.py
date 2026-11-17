"""一次连接内，逐个 3404 试戴候选称号，记录哪些 result=0（可戴/拥有）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.provider import SeerApiProvider

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
p = SeerApiProvider()

# 候选：强攻/高体力的属性称号（id 来自 seerapi 能力加成列表）
CAND = [300, 268, 337, 368, 397, 467, 493, 591, 607, 543, 526, 545, 435, 494, 405, 439, 479, 283, 435, 436, 476, 522, 564, 574, 472, 329, 417]


def nm(tid):
    d = p.get("title", tid)
    return (d.get("name") if d else str(tid)), (d.get("ability_desc") if d else "")


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    owned = []
    loop = asyncio.get_running_loop()
    for tid in CAND:
        await c.send(3404, [struct.pack(">I", tid)])
        # 读随后 3404 回执
        end = loop.time() + 1.5
        result = None
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == 3404:
                result = f.result
                break
        name, desc = nm(tid)
        mark = "OK" if result == 0 else f"X({result})"
        print(f"{tid}  {name}  [{desc}] -> {mark}")
        if result == 0:
            owned.append(tid)
        await asyncio.sleep(0.2)

    # 恢复回 417 夏日狂想曲
    await c.send(3404, [struct.pack(">I", 417)])
    await asyncio.sleep(0.5)
    await c.close()
    print(f"\n可戴(拥有)的属性称号：{owned}")


asyncio.run(main())