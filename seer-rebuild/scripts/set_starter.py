"""设首发(2308)一次，并回读背包确认。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData


def u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


async def main() -> None:
    account, password, catch = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    await c.send(2308, [u32(catch)])
    print(f"[sent] 2308 设首发 catch={catch} (0x{catch:08x})")
    end = loop.time() + 2.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd in (2308, 43706) or f.result != 0:
            print(f"    [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:24].hex()}")

    await c.send(43706, [])
    data = BattleData(r"F:\seer\seer_cfg\json")
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706:
            cnt, pets = parse_bag_43706(f.body, data=data)
            print("正式:")
            for p in pets[:cnt]:
                nm = data.species.get(p.species_id)
                print(f"  {nm.name if nm else p.species_id} catch={p.catch_time} (0x{p.catch_time:08x})")
            print("待命:")
            for p in pets[cnt:]:
                nm = data.species.get(p.species_id)
                print(f"  {nm.name if nm else p.species_id} catch={p.catch_time} (0x{p.catch_time:08x})")
            break
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())