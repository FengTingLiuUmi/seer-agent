"""正确会话握手：读 S2C 的 2002 token → 45963 回传 → 46046 → 43706。"""
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
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    # 1) 收登录推送，找 2002 token / 1001 快照
    token = None
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        print(f"recv cmd={f.cmd} len={len(f.body)} body={f.body[:16].hex()}")
        if f.cmd == 2002 and len(f.body) >= 4:
            token = f.body[:4]
            print(f"  ★ 2002 token = {token.hex()}")
            break

    if token is None:
        print("没拿到 2002 token，尝试 1002 心跳")
        await c.send(1002, [])
        end = loop.time() + 4.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            print(f"recv cmd={f.cmd} len={len(f.body)} body={f.body[:16].hex()}")
            if f.cmd in (2002, 1002) and len(f.body) >= 4:
                token = f.body[:4]
                break
        if token is None:
            token = b"\x00\x00\x00\x00"

    # 2) 回传 token + 发业务命令
    await c.send(45963, [u32(2) + u32(1) + token])
    print(f"[send] 45963 回传 token={token.hex()}")
    await asyncio.sleep(0.5)
    await c.send(46046, [u32(4) + u32(0x0B61) + u32(0x0B62) + u32(0x31E8) + u32(0x31E9)])
    print("[send] 46046")
    await asyncio.sleep(0.5)
    await c.send(43706, [])
    print("[send] 43706")

    # 3) 收响应
    end = loop.time() + 10.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        mark = " <<<" if f.cmd in (43706, 2361, 2301) else ""
        print(f"recv cmd={f.cmd} len={len(f.body)}{mark}")
        if mark:
            print(f"     body前32={f.body[:32].hex()}")

    await c.close()


asyncio.run(main())