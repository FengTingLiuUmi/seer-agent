import asyncio, os, struct
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

# 当前被我改成正式的三只（帝皇/六界/希瓦）放回仓库
MOVE_OUT = [0x62D8B735, 0x62EF6F18, 0x6A197A40]
# 原始正式6只还原
MOVE_IN = [1719587365, 1665079804, 1623393109, 1612845444, 1611890126, 1472551551]
STARTER = 1719587365  # 星光·丽莎布布


async def main():
    sess = authenticate(os.environ["SEER_ACCOUNT"], os.environ["SEER_PASSWORD"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    async def send_wait(cmd, body, dur=1.2, tag=""):
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
        print(f"  [{tag}] cmd={cmd} body={body.hex() if body else ''} -> " + "; ".join(recs))

    await send_wait(41228, struct.pack(">I", 0x6AFE0B1E), tag="开自动恢复")
    await send_wait(47136, b"", dur=2.0, tag="治疗回满")
    for ct in MOVE_OUT:
        await send_wait(2304, struct.pack(">II", ct, 0), tag="放回仓库")
    for ct in MOVE_IN:
        await send_wait(2304, struct.pack(">II", ct, 1), tag="加入正式")
    await send_wait(2308, struct.pack(">I", STARTER), dur=1.5, tag="设首发")
    await c.close()


asyncio.run(main())