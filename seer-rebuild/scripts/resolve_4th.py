"""在线：43706 拿背包，再用候选个体id发 2301 反查，定位第4只时空界神(4050)的个体id。"""
import asyncio
import struct
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

KNOWN = {3512: "帝皇之御", 3045: "六界神王", 5000: "圣灵谱尼", 4050: "时空界神"}


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def log(s):
    print(s, flush=True)


def is_catch(v):
    return 0x54A00000 <= v <= 0x6C000000


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity", logger=log)
    await c.connect(timeout=20.0)
    if not c.connected:
        log("FAIL connect")
        return

    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    token = getattr(c, "token", b"\x00\x00\x00\x00")

    body = None
    # 收 43706
    end = loop.time() + 8.0
    while loop.time() < end and body is None:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706:
            body = f.body
        elif f.cmd in (2002, 1002) and len(f.body) >= 4:
            token = f.body[:4]

    if body is None:
        log("FAIL no 43706")
        await c.close()
        return

    # 从 43706 解析 (species, catch) 对（非对齐扫描）
    span = 0x94
    found = {}
    for off in range(0, len(body) - span - 4):
        spp = struct.unpack_from(">I", body, off)[0]
        ct = struct.unpack_from(">I", body, off + span)[0]
        if 1 <= spp <= 6000 and is_catch(ct):
            found[ct] = spp
    log(f"[43706] count={struct.unpack_from('>I', body, 0)[0]} found={ {KNOWN.get(s, s): hex(c) for c, s in found.items()} }")

    # 候选 catch：43706 body 里所有 unix 范围值（去重）
    cands = []
    seen = set()
    for off in range(0, len(body) - 3):
        v = struct.unpack_from(">I", body, off)[0]
        if is_catch(v) and v not in seen:
            seen.add(v)
            cands.append(v)
    log(f"[candidates] {len(cands)}: {[hex(x) for x in cands]}")

    # 逐个 2301 反查，已经知道 species 的跳过
    resolved = dict(found)
    for uid in cands:
        if uid in resolved:
            continue
        await c.send(2301, [u32(uid)])
        end = loop.time() + 2.0
        got = None
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2301 and len(f.body) >= 4:
                spp = struct.unpack_from(">I", f.body, 0)[0]
                if 1 <= spp <= 6000:
                    got = spp
            elif f.cmd in (2002, 1002) and len(f.body) >= 4:
                token = f.body[:4]
        if got:
            resolved[uid] = got
            log(f"[2301] uid={hex(uid)} -> species {got} ({KNOWN.get(got, '?')})")
        else:
            log(f"[2301] uid={hex(uid)} -> no species")

    # 汇总
    log("\n===== 汇总 =====")
    final = {s: ct for ct, s in resolved.items()}
    for spp in sorted(final):
        log(f"  species {spp} ({KNOWN.get(spp,'?')}) catch={hex(final[spp])}")

    await c.close()


if __name__ == "__main__":
    asyncio.run(main())