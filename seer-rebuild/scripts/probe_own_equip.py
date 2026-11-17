"""只读探测：找「已拥有装备/装扮/套装」列表命令。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


async def main() -> None:
    account, password = sys.argv[1], sys.argv[2]
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    # 候选「已拥有装备/道具/图鉴」读取命令（空 body）
    probes = [41301, 42399, 45555, 9019, 40001, 41006, 42378, 41206, 45543, 45807]
    for cmd in probes:
        try:
            await c.send(cmd, [])
        except Exception as e:
            print(f"[send {cmd}] err {e}")
            continue
        got = None
        end = loop.time() + 2.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == cmd:
                got = f
                break
        if got is not None:
            print(f"cmd={cmd} 响应 len={len(got.body)} result={got.result} body={got.body[:96].hex()}")
        else:
            print(f"cmd={cmd} 无响应")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())