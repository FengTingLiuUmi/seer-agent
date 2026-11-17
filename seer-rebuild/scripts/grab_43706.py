"""抓当前背包的原始 43706 body 并落盘，同时定位 4 只已知精灵的 species 出现位置。"""
import asyncio
import struct
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

OUT = ROOT / "live_43706.bin"
KNOWN = {3512: "帝皇之御", 3045: "六界神王", 5000: "圣灵谱尼", 4050: "时空界神"}


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def log(s):
    print(s, flush=True)


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity", logger=log)
    await c.connect(timeout=20.0)
    if not c.connected:
        log("FAIL not connected")
        return

    await c.send(43706, [])

    loop = asyncio.get_running_loop()
    token = getattr(c, "token", b"\x00\x00\x00\x00")
    bodies = []
    end = loop.time() + 12.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706:
            bodies.append(f.body)
            log(f"[43706] len={len(f.body)} count={struct.unpack_from('>I', f.body, 0)[0] if len(f.body)>=4 else None}")
        elif f.cmd in (2002, 1002) and len(f.body) >= 4:
            token = f.body[:4]
            try:
                await c.send(45963, [u32(2) + u32(1) + token])
            except Exception:
                break

    await c.close()
    if not bodies:
        log("NO 43706 body received")
        return
    body = bodies[0]
    OUT.write_bytes(body)
    log(f"saved {OUT} len={len(body)}")
    # 定位 4 只
    log("---- species locations (byte offset -> u32) ----")
    for i in range(0, len(body) - 3):
        v = struct.unpack_from(">I", body, i)[0]
        if v in KNOWN:
            log(f"  offset 0x{i:03x}: species {v} ({KNOWN[v]})")
    # 所有 catch-time 候选
    log("---- catch_time candidates ----")
    for i in range(0, len(body) - 3):
        v = struct.unpack_from(">I", body, i)[0]
        if 0x54A00000 <= v <= 0x6C000000:
            log(f"  offset 0x{i:03x}: 0x{v:08x} ({v})")


if __name__ == "__main__":
    asyncio.run(main())