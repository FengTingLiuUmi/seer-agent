"""验证：登录后先发 1002 心跳，再发 1016+43706 读精灵，看是否还被踢。"""
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

    # 先发一次 1002 心跳
    await c.send(1002, [])
    print("[send] 1002 心跳")

    # 发 1016 会话
    await c.send(1016, [2])
    print("[send] 1016 会话")

    # 收 2 秒
    end = loop.time() + 2.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        print(f"  recv cmd={f.cmd} result={f.result} len={len(f.body)}")

    # 发 43706 读精灵
    try:
        await c.send(43706, [])
        print("[send] 43706 读精灵")
    except (ConnectionError, asyncio.IncompleteReadError) as e:
        print("[踢线] 43706 发送失败:", e)
        await c.close()
        return

    # 收 6 秒
    end = loop.time() + 6.0
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