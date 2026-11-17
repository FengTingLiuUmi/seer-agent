"""在线背包诊断：连接 + 登录握手 + 背包命令，逐帧打印，定位 count=0 卡在哪一步。"""
import asyncio
import struct
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def log(s):
    print(s, flush=True)


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    log(f"[auth] uid={sess.uid} session={sess.session[:6]}...{sess.session[-4:]}")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity", logger=log)
    first = await c.connect(timeout=20.0)
    log(f"[connect] first_1001={first.cmd if first else None} result={first.result if first else 'N/A'} "
        f"body_len={len(first.body) if first else 0} connected={c.connected} token={getattr(c,'token',b'').hex()}")

    if not c.connected:
        log("[FAIL] not connected")
        await c.close()
        return

    # 背包命令序列（同 read_bag）
    await c.send(46046, [u32(4) + u32(0x0B61) + u32(0x0B62) + u32(0x31E8) + u32(0x31E9)])
    await c.send(43706, [])

    loop = asyncio.get_running_loop()
    token = getattr(c, "token", b"\x00\x00\x00\x00")
    end = loop.time() + 20.0
    seen = {}
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        seen[f.cmd] = seen.get(f.cmd, 0) + 1
        head = f.body[:48].hex()
        log(f"[recv] cmd={f.cmd} result={f.result} len={len(f.body)} n={seen[f.cmd]} head={head}")
        if f.cmd in (2002,) and len(f.body) >= 4:
            token = f.body[:4]
            log(f"  -> new token {token.hex()}")
    log(f"[summary] seen cmds = {seen}")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())