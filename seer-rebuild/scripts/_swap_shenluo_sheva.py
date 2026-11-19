import asyncio, os, struct
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

REMOVE = 0x5FF913DE   # 神罗 放回
ADD = 0x6A197A40      # 希瓦 加入正式


async def main():
    sess = authenticate(os.environ["SEER_ACCOUNT"], os.environ["SEER_PASSWORD"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    async def send_wait(cmd, body, dur=1.3):
        await c.send(cmd, [body] if body else [])
        end = loop.time() + dur
        recs = []
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            recs.append(f"cmd={f.cmd} r={f.result}")
            if f.cmd == cmd and f.result != 0:
                break
        print(f"  [sent] cmd={cmd} body={body.hex() if body else ''} -> " + "; ".join(recs))

    await send_wait(2304, struct.pack(">II", REMOVE, 0))   # 神罗 放回仓库
    await send_wait(2304, struct.pack(">II", ADD, 1))      # 希瓦 加入正式
    await c.close()


asyncio.run(main())