"""读普通仓库 2303[0,1000]，用 16 字节/项解析，定位 阿布(31)/艾夏拉(3673)/重生之翼(2987) 的真实 catch。"""
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
WANT = {3976: "阿徒", 3673: "艾夏拉", 2987: "重生之翼"}


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
    # 分页读普通仓库：offset, count
    for offset in (0, 1000, 2000, 3000):
        await c.send(2303, [u32(offset) + u32(1000)])
        loop = asyncio.get_running_loop()
        end = loop.time() + 12.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd != 2303 or len(f.body) < 4:
                continue
            count = struct.unpack_from(">I", f.body, 0)[0]
            log(f"[2303 offset={offset}] count={count}")
            hit = 0
            for k in range(count):
                off = 4 + k * 16
                if off + 16 > len(f.body):
                    break
                a = struct.unpack_from(">I", f.body, off)[0]
                if a in WANT:
                    b, catch, d = struct.unpack_from(">III", f.body, off + 4)
                    name = DATA.species.get(a).name if a in DATA.species else "?"
                    log(f"  >>> species={a} {name} catch=0x{catch:x}({catch})  words=[{a},{b},{catch:#x},{d:#x}]")
                    hit += 1
            if count < 1000:
                break
            if hit == 0 and count == 0:
                pass
            break  # 一次 offset 读一个批次即可
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())