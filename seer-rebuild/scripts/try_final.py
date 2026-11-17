"""验证：新 token 握手后发 46046→43706，能否收到背包响应。"""
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
    print("connect 完成, 1001 result =", first.result if first else None)

    loop = asyncio.get_running_loop()

    # 发 46046（4 ids）+ 43706
    await c.send(46046, [u32(4) + u32(0x0B61) + u32(0x0B62) + u32(0x31E8) + u32(0x31E9)])
    print("[send] 46046")
    await asyncio.sleep(0.5)
    await c.send(43706, [])
    print("[send] 43706")

    # 收响应
    end = loop.time() + 8.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        mark = " ★" if f.cmd in (43706, 2361, 2301) else ""
        print(f"recv cmd={f.cmd} len={len(f.body)}{mark}")
        if mark:
            print(f"     body头={f.body[:40].hex()}")
            if f.cmd == 43706 and len(f.body) >= 8:
                print(f"     count={struct.unpack_from('>I', f.body, 0)[0]}")

    await c.close()


asyncio.run(main())