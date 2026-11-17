"""查错误码 1940033 + 当前正式栏位（43706）。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.battle_data import BattleData
from seer_rebuild.pets import parse_bag_43706

p = SeerApiProvider()
for code in [1940033, 1940034, 1940032, 1940030, 1940031]:
    d = p.get("error_code", code, fields=["id", "name", "desc"])
    print(code, "->", d)

DATA = BattleData(r"F:\seer\seer_cfg\json")


def nm(s):
    sp = DATA.species.get(s)
    return sp.name if sp else str(s)


async def main():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    await c.send(43706, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    body = b""
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 43706 and len(f.body) >= 4:
            body = f.body
            break
    await c.close()
    cnt = struct.unpack_from(">I", body, 0)[0] if body else -1
    cnt2, pets = parse_bag_43706(body, data=DATA) if body else (0, [])
    print(f"\n43706 head count={cnt} len={len(body)} 解析到{len(pets)}只：")
    for pt in pets:
        print(f"  {nm(pt.species_id)} species={pt.species_id} catch={pt.catch_time:#x}")


asyncio.run(main())