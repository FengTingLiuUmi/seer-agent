import asyncio, os, struct
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

CLEAR = [1719587365, 1665079804, 1623393109, 1612845444, 1611890126, 1472551551]  # 当前正式6只
ADD = [0x62D8B735, 0x62EF6F18, 0x5FF913DE]  # 帝皇之御 / 六界神王 / 神罗
STARTER = 0x62D8B735  # 帝皇之御 首发


async def main():
    sess = authenticate(os.environ["SEER_ACCOUNT"], os.environ["SEER_PASSWORD"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    async def send_wait(cmd, body, dur=1.5):
        await c.send(cmd, [body] if body else [])
        end = loop.time() + dur
        recs = []
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            recs.append(f"cmd={f.cmd} r={f.result}")
        print(f"  [sent] cmd={cmd} body={body.hex() if body else ''}")
        for r in recs:
            print(f"    [recv] {r}")

    for ct in CLEAR:
        await send_wait(2304, struct.pack(">II", ct, 0), dur=1.2)  # 放回仓库
    for ct in ADD:
        await send_wait(2304, struct.pack(">II", ct, 1), dur=1.2)  # 加入正式
    await send_wait(2308, struct.pack(">I", STARTER), dur=1.5)     # 设首发
    await c.close()


asyncio.run(main())