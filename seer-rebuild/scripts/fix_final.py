"""微调：帝皇之御降待命(flag4)，启灵元神进正式(flag1)。"""
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
    account, password = sys.argv[1], sys.argv[2]
    steps = [
        ("帝皇之御降待命", 1658369845, 4),
        ("启灵元神进正式", 1623393109, 1),
    ]
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()
    for label, ct, flag in steps:
        await c.send(2304, [u32(ct) + u32(flag)])
        print(f"[sent] {label} catch={ct} flag={flag}")
        end = loop.time() + 1.2
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2304 or f.result != 0:
                print(f"    [recv] cmd={f.cmd} result={f.result} len={len(f.body)}")
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
                print(f"  {nm.name if nm else p.species_id} catch={p.catch_time}")
            print("待命:")
            for p in pets[cnt:]:
                nm = data.species.get(p.species_id)
                print(f"  {nm.name if nm else p.species_id} catch={p.catch_time}")
            break
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())