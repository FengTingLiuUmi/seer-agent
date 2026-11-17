"""只读：一次登录读多只精灵的 2301 详情（level / 能力 / 装备技能）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pet_details import parse_2301


async def main(account: str, password: str, catch_times: list[int]) -> None:
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    for ct in catch_times:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])
        detail = None
        end = loop.time() + 6.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=0.8)
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2301:
                detail = parse_2301(f.body)
                break
        if detail is None:
            print(f"catch={ct} (0x{ct:08x}): 无响应")
        else:
            print(f"catch={ct} (0x{ct:08x}) species={detail.species_id} level={detail.level} "
                  f"HP={detail.max_hp}/{detail.cur_hp} 物攻={detail.atk} 物防={detail.def_} "
                  f"特攻={detail.sp_atk} 特防={detail.sp_def} 速={detail.spd} 技能={detail.skills}")
    await c.close()


if __name__ == "__main__":
    acct = sys.argv[1]
    pw = sys.argv[2]
    cts = [int(x, 0) for x in sys.argv[3:]]
    asyncio.run(main(acct, pw, cts))