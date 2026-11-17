import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
import asyncio

p = SeerApiProvider()
try:
    d = p.get("error_code", 103207, fields=["id", "name", "desc"])
    print("103207 ->", d)
except Exception as e:
    print("103207 err:", e)


async def read_equip_inv():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    # 42399 = MULTI_ITEM_LIST（装备列表）；试读一批装备 id
    ids = [1300724, 1300725, 1300726, 1300727, 1300670, 1300671, 1300672, 1300673, 1301040, 1300954]
    body = struct.pack(">I", len(ids)) + b"".join(struct.pack(">I", i) for i in ids)
    await c.send(42399, [body])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 42399:
            print("42399 响应:", f.body.hex())
            break
    await c.close()


asyncio.run(read_equip_inv())