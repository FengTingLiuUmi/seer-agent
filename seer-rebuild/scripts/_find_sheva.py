import asyncio, os, struct
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


async def main():
    sess = authenticate(os.environ["SEER_ACCOUNT"], os.environ["SEER_PASSWORD"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()
    needle = struct.pack(">I", 3865)
    for off in (0, 200, 400, 600, 800):
        await c.send(2303, [struct.pack(">II", off, 200)])
        body = None
        end = loop.time() + 6.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2303:
                body = f.body
                break
        if body is None:
            print(f"off={off}: 无响应")
            break
        head = struct.unpack_from(">I", body, 0)[0] if len(body) >= 4 else -1
        hits = [i for i in range(len(body) - 3) if body[i:i + 4] == needle]
        print(f"off={off}: len={len(body)} head_u32={head} 3865出现位置={hits[:5]}")
        if not hits and head < 200:
            break
    await c.close()


asyncio.run(main())