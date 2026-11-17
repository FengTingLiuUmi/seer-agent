"""恢复原始阵容：圣灵谱尼首发 + 西游四 + 启灵元神，帝皇之御回待命。"""
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
    # (标签, cmd, catch, flag)  flag 对 2304: 0正式->仓库,1仓库->正式; 2308 用 None
    steps = [
        ("六界神王放回仓库", 2304, 1659858712, 0),
        ("时空界皇放回仓库", 2304, 1610423766, 0),
        ("圣灵谱尼设为首发", 2308, 1472551551, None),
        ("天河神将加入正式", 2304, 1611350067, 1),
        ("三藏加入正式", 2304, 1611349897, 1),
        ("启灵元神加入正式", 2304, 1623393109, 1),
    ]
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    for label, cmd, ct, flag in steps:
        body = u32(ct) if cmd == 2308 else u32(ct) + u32(flag)
        await c.send(cmd, [body])
        print(f"[sent] {label}")
        end = loop.time() + 1.2
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd in (2308, 2304) or f.result != 0:
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