"""只读诊断：进入简单难度(1)后只发 2404，不收 2405，看战斗是否初始化。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


NOISE = {1002, 45963, 8002, 3452, 4395, 2002, 2001, 2441, 42494, 1016}


async def main():
    account, password, diff = sys.argv[1], sys.argv[2], int(sys.argv[3])
    sess = authenticate(account, password)
    h, p = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = h, p, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    body = u32(266) + u32(diff)
    await c.send(41284, [body])
    print("[sent] 41284 进关")
    await asyncio.sleep(1.0)
    await c.send(41282, [body])
    print("[sent] 41282 开战")
    await asyncio.sleep(1.5)
    await c.send(2404, [])
    print("[sent] 2404 准备")

    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd in NOISE:
            continue
        print(f"[recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:60].hex()}")
    print("[done] 收帧结束")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())