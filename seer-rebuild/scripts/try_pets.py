"""登录 → 发 1016 会话握手 → 发 43706 读精灵，观察是否有响应。"""
import asyncio

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    loop = asyncio.get_running_loop()

    # 发 1016（GET_SESSION_KEY，body=00000002）
    for cmd, args in [(1016, [2]), (43706, []), (46046, [b"\x00\x00\x00\x02\x00\x00\x0b\x05\x00\x01\xe4\xb6"])]:
        await c.send(cmd, args)
        print(f"[send] cmd={cmd}")
        end = loop.time() + 5.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            mark = "  <<<" if f.cmd not in (3452, 8002, 45827, 1001, 4395, 2002) else ""
            print(f"  recv cmd={f.cmd} result={f.result} len={len(f.body)}{mark}")
            if f.cmd not in (3452, 8002, 45827, 1001, 4395, 2002):
                print(f"       body={f.body[:120].hex()}")

    await c.close()


asyncio.run(main())