import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"
CHECK = [(3567, 0x640CB1EA), (4510, 0x648604F2), (3697, 0x60256A50), (3670, 0x60584634), (4169, 0x5FF913DE)]


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    await c.send(43706, [])
    await asyncio.sleep(1.0)
    for sp, ct in CHECK:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])
    loop = asyncio.get_running_loop()
    end = loop.time() + 12.0
    got = {}
    while loop.time() < end and len(got) < len(CHECK):
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2301 and len(f.body) >= 0x50:
            sp = struct.unpack_from(">I", f.body, 0)[0]
            lv = struct.unpack_from(">I", f.body, 0x24)[0]
            hp = struct.unpack_from(">I", f.body, 0x34)[0]
            atk = struct.unpack_from(">I", f.body, 0x3c)[0]
            spa = struct.unpack_from(">I", f.body, 0x44)[0]
            spd = struct.unpack_from(">I", f.body, 0x4c)[0]
            got[sp] = (lv, hp, atk, spa, spd)
    await c.close()
    for sp, ct in CHECK:
        if sp in got:
            lv, hp, atk, spa, spd = got[sp]
            print(f"{sp} catch={hex(ct)} lv={lv} HP={hp} 物攻={atk} 特攻={spa} 速度={spd}")


asyncio.run(main())