"""只在一次登录里执行阵容调整(2304/2308)并回读背包验证。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData

RELEASE = 2304
GET_PETS = 43706
SET_DEFAULT = 2308


def u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


async def main() -> None:
    account, password = sys.argv[1], sys.argv[2]
    # 步骤：(标签, catch_time, flag)   flag: 0 正式->仓库 / 1 仓库->正式 / 2 待命,3 清待命,4 降待命
    # 用 "S" 表示 2308 设首发
    steps = [
        ("清正式-天河神将", 1611350067, 0),
        ("清正式-三藏", 1611349897, 0),
        ("清正式-启灵元神", 1623393109, 0),
        ("加正式-六界神王", 1659858712, 1),
        ("加正式-时空界皇", 1610423766, 1),
        ("首发-帝皇之御", 1658369845, "S"),
    ]

    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    for label, ct, flag in steps:
        if flag == "S":
            await c.send(SET_DEFAULT, [u32(ct)])
            print(f"[sent] 2308 {label} catch={ct}")
        else:
            await c.send(RELEASE, [u32(ct) + u32(flag)])
            print(f"[sent] 2304 {label} catch={ct} flag={flag}")
        # 每步之间吸收 S2C result 链
        end = loop.time() + 1.2
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd in (2304, 2308, 43706) or f.result != 0:
                print(f"    [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:24].hex()}")

    # 回读背包
    await c.send(GET_PETS, [])
    await asyncio.sleep(1.0)
    data = BattleData(r"F:\seer\seer_cfg\json")
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == GET_PETS:
            cnt, pets = parse_bag_43706(f.body, data=data)
            formal = pets[:cnt]
            reserve = pets[cnt:]
            print("\n[背包回读]")
            print(f"正式({len(formal)}):")
            for p in formal:
                nm = data.species.get(p.species_id)
                print(f"  {nm.name if nm else p.species_id} species={p.species_id} catch={p.catch_time} (0x{p.catch_time:08x})")
            print(f"待命({len(reserve)}):")
            for p in reserve:
                nm = data.species.get(p.species_id)
                print(f"  {nm.name if nm else p.species_id} species={p.species_id} catch={p.catch_time} (0x{p.catch_time:08x})")
            break
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())