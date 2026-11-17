"""抓当前 43706 raw body（6正式+5待命）并 dump 块结构，定位正式/待命分界。"""
import asyncio
import struct
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.battle_data import BattleData

OUT = ROOT / "live_43706_v2.bin"
DATA = BattleData(r"F:\seer\seer_cfg\json")


def log(s):
    print(s, flush=True)


def is_catch(v):
    return 0x54A00000 <= v <= 0x6C000000


def find_blocks(body):
    """块首启发式：species已知 + species后8字节零 + catch@+0x94 低16位非0。"""
    out = []
    for off in range(0, len(body) - 0x94 - 4):
        species = struct.unpack_from(">I", body, off)[0]
        if not (1 <= species <= 6000) or species not in DATA.species:
            continue
        if body[off + 4:off + 12] != b"\x00" * 8:
            continue
        catch = struct.unpack_from(">I", body, off + 0x94)[0]
        if not is_catch(catch) or (catch & 0xFFFF) == 0:
            continue
        out.append((off, species, DATA.species[species].name, catch))
    return out


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
    body = None
    end = loop.time() + 12.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706:
            body = f.body
            break
    await c.close()
    if body is None:
        log("FAIL no 43706")
        return

    OUT.write_bytes(body)
    log(f"saved {OUT} len={len(body)}")
    log(f"count@0x00 = {struct.unpack_from('>I', body, 0)[0]}")
    log(f"u32@0x04 = {struct.unpack_from('>I', body, 4)[0]}")

    blocks = find_blocks(body)
    log(f"\n块首候选 {len(blocks)} 个：")
    prev = None
    for off, spp, name, catch in blocks:
        gap = f"+{off - prev:#x}" if prev is not None else ""
        prev = off
        log(f"  @0x{off:04x}{gap}  species={spp} {name}  catch={catch:#x}")

    # dump body 里出现的所有 count-like 小整数（可能是第二列表 count）
    log("\nbody 里 1..20 的 u32（找第二个 count）：")
    for off in range(0, min(len(body) - 3, 0x800), 4):
        v = struct.unpack_from(">I", body, off)[0]
        if 1 <= v <= 20:
            log(f"  @0x{off:04x} = {v}")
        if off >= 0x800:
            break


if __name__ == "__main__":
    asyncio.run(main())