"""在线读仓库(2361)，定位 阿布/艾夏拉/重生之翼 的 catch_time。只读。"""
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
WANT = {3976: "阿徒", 2987: "重生之翼", 3673: "艾夏拉"}


def log(s):
    print(s, flush=True)


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity", logger=log)
    await c.connect(timeout=20.0)
    if not c.connected:
        log("FAIL connect")
        return

    await c.send(2361, [])  # GET_LOVE_PET_LIST
    loop = asyncio.get_running_loop()
    end = loop.time() + 12.0
    found = {}
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd != 2361 or len(f.body) < 4:
            continue
        count = struct.unpack_from(">I", f.body, 0)[0]
        log(f"[2361] count={count} len={len(f.body)}")
        for k in range(count):
            off = 4 + k * 12
            if off + 12 > len(f.body):
                break
            spp = struct.unpack_from(">I", f.body, off)[0]
            flag = struct.unpack_from(">I", f.body, off + 4)[0]
            catch = struct.unpack_from(">I", f.body, off + 8)[0]
            if spp in WANT:
                name = DATA.species.get(spp).name if spp in DATA.species else "?"
                found.setdefault(spp, []).append((catch, flag))
        break

    await c.close()
    print("\n=== 目标精灵在仓库中的 catch_time ===")
    for spp in WANT:
        lst = found.get(spp, [])
        for catch, flag in lst:
            print(f"  species={spp} {WANT[spp]} catch=0x{catch:x}({catch}) flag={flag}")


if __name__ == "__main__":
    asyncio.run(main())