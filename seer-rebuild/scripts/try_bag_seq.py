"""在线复刻「打开背包」命令序列，验证能否收到 43706 响应。"""
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

    # 复刻打开背包（跳过 45963 轮询，hash 是服务端相关拿不到）
    seq = [
        ("41228", 41228, u32(0x6AF909EA)),
        ("46046", 46046, u32(4) + u32(0x0B61) + u32(0x0B62) + u32(0x31E8) + u32(0x31E9)),
        ("43706", 43706, b""),
    ]
    for name, cmd, body in seq:
        await c.send(cmd, [body] if body else [])
        print(f"[send] {name}({cmd})")
        end = loop.time() + 3.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            mark = " <<<" if f.cmd not in (3452, 8002, 45827, 1001, 4395, 2002, 45963, 2001) else ""
            print(f"  recv cmd={f.cmd} result={f.result} len={len(f.body)}{mark}")
            if mark:
                print(f"       body头={f.body[:40].hex()}")
    await c.close()


asyncio.run(main())