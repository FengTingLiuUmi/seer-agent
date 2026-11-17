"""按身体顺序列出当前 43706 的正式/待命（正式=前 count 块）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.battle_data import BattleData

DATA = BattleData(r"F:\seer\seer_cfg\json")


def nm(s):
    sp = DATA.species.get(s)
    return sp.name if sp else str(s)


def scan_blocks(body):
    """顺序扫描：species + 8零 + 148B 后 catch。"""
    out = []
    seen = set()
    span = 0x94
    for off in range(len(body) - span - 4):
        s = struct.unpack_from(">I", body, off)[0]
        if not (1 <= s <= 6000):
            continue
        if body[off + 4:off + 12] != b"\x00" * 8:
            continue
        ct = struct.unpack_from(">I", body, off + span)[0]
        if ct in seen:
            continue
        seen.add(ct)
        out.append((off, s, ct))
    return out


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    body = b""
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706 and len(f.body) >= 4:
            body = f.body
            break
    await c.close()
    cnt = struct.unpack_from(">I", body, 0)[0]
    blocks = scan_blocks(body)
    print(f"43706 head cnt={cnt} len={len(body)} 共{len(blocks)}块:")
    for i, (off, s, ct) in enumerate(blocks):
        tag = "正式" if i < cnt else "待命"
        print(f"  [{tag}] {nm(s)} species={s} catch={hex(ct)} @off={off}")


asyncio.run(main())