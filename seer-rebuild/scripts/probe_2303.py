"""探测 2303 GET_PET_LIST(普通仓库) 的参数，找 阿布(31)。只读。"""
import asyncio
import struct
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
sys.path.insert(0, str(ROOT))

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.battle_data import BattleData

DATA = BattleData(r"F:\seer\seer_cfg\json")


def u32(v):
    return struct.pack(">I", v & 0xFFFFFFFF)


def log(s):
    print(s, flush=True)


async def probe(body: bytes):
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity", logger=log)
    await c.connect(timeout=20.0)
    if not c.connected:
        log("FAIL connect")
        return
    await c.send(2303, [body])
    loop = asyncio.get_running_loop()
    end = loop.time() + 8.0
    got = False
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2303 and len(f.body) >= 4:
            count = struct.unpack_from(">I", f.body, 0)[0]
            log(f"[2303] count={count} len={len(f.body)}")
            for k in range(count):
                off = 4 + k * 12
                if off + 12 > len(f.body):
                    break
                spp = struct.unpack_from(">I", f.body, off)[0]
                catch = struct.unpack_from(">I", f.body, off + 8)[0]
                if spp == 31:
                    name = DATA.species.get(spp).name if spp in DATA.species else "?"
                    log(f"  >>> 阿布 species=31 catch=0x{catch:x}({catch}) 存在于普通仓库")
            got = True
        elif f.cmd not in (1002, 2002, 45963, 8002, 3452, 45827, 4395) and len(f.body):
            log(f"[other] cmd={f.cmd} len={len(f.body)}")
    if not got:
        log("[2303] 无 2303 响应（可能参数不对/EOF）")
    await c.close()


async def main():
    for body in (u32(0) + u32(100), u32(0) + u32(1000), u32(1) + u32(0), u32(100)):
        print(f"\n===== 2303 body={body.hex()} =====")
        try:
            await probe(body)
        except Exception as e:
            print(f"  probe error: {e}")


if __name__ == "__main__":
    asyncio.run(main())