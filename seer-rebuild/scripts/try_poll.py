"""完整 token 轮询：43706 请求后，用 45963 轮询取精灵数据。"""
import asyncio
import struct

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    first = await c.connect(timeout=15.0)
    print("connect ok, result =", first.result if first else None)
    loop = asyncio.get_running_loop()

    token = b"\x00\x00\x00\x00"

    async def pump(seconds):
        nonlocal token
        end = loop.time() + seconds
        got = []
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd in (2002, 1002) and len(f.body) >= 4:
                token = f.body[:4]
            got.append((f.cmd, len(f.body), f.body[:16].hex()))
        return got

    # 发 46046 + 43706
    await c.send(46046, [u32(4) + u32(0xB61) + u32(0xB62) + u32(0x31E8) + u32(0x31E9)])
    await c.send(43706, [])
    print("[send] 46046 + 43706")

    # 轮询：多次发 45963 回传 token
    for rnd in range(6):
        await c.send(45963, [u32(2) + u32(1) + token])
        got = await pump(2.0)
        for cmd, ln, h in got:
            mark = " ★" if cmd not in (2002, 2001, 2101, 1002, 3452) else ""
            print(f"  r{rnd} recv cmd={cmd} len={ln}{mark} head={h}")
            if mark and ln > 100:
                print(f"        body={h}")
        await asyncio.sleep(0.3)

    await c.close()


asyncio.run(main())