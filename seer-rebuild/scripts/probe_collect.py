"""只读诊断：尝试 41413 领取/结算，看能否解锁下一轮简单。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def list_body(ids):
    return u32(len(ids)) + b"".join(u32(x) for x in ids)


NOISE = {1002, 45963, 8002, 3452, 4395, 2002, 2001, 2441, 42494, 1016}


async def main():
    account, password = sys.argv[1], sys.argv[2]
    sess = authenticate(account, password)
    h, p = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = h, p, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    await c.send(46046, [list_body([303274, 303275, 303272])])
    print("[sent] 46046 读状态")
    await asyncio.sleep(1.0)

    await c.send(41413, [u32(2400611) + u32(1) + u32(0)])
    print("[sent] 41413 领取 factor=2400611 action=(1,0)")

    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd in NOISE:
            continue
        print(f"[recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:80].hex()}")
    print("[done]")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())