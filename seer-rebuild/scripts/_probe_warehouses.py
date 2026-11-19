import asyncio, json, os, struct
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pets import parse_pet_list

TARGETS = {3512: "帝皇之御", 3045: "六界神王", 3865: "希瓦", 3463: "时空界皇",
           3866: "月照星魂", 3567: "魔钰", 4377: "蒂朵", 3329: "六界帝神",
           4169: "弑序神罗", 5000: "圣灵谱尼"}


def parse_2303(body):
    out = []
    if len(body) < 4:
        return out
    n = struct.unpack_from(">I", body, 0)[0]
    for k in range(n):
        off = 4 + k * 16
        if off + 16 > len(body):
            break
        species, flag, catch, level = struct.unpack_from(">IIII", body, off)
        out.append((species, flag, catch, level))
    return out


async def main():
    sess = authenticate(os.environ["SEER_ACCOUNT"], os.environ["SEER_PASSWORD"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    # 精英仓库 2361
    await c.send(2361, [])
    elite = []
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2361:
            elite = parse_pet_list(f.body)
            break

    # 普通仓库 2303 分页
    normal = []
    for off in (0, 200, 400, 600):
        await c.send(2303, [struct.pack(">II", off, 200)])
        got = None
        end = loop.time() + 6.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2303:
                got = parse_2303(f.body)
                break
        if not got:
            break
        normal += got
        if len(got) < 200:
            break
    await c.close()

    print("== 精英仓库(2361) 目标命中 ==")
    for e in sorted(elite, key=lambda x: x.species_id):
        if e.species_id in TARGETS:
            print(f"  {e.species_id} {TARGETS[e.species_id]} flag={e.flag} catch_time={e.catch_time} (0x{e.catch_time:08x})")
    print("== 普通仓库(2303) 目标命中 ==")
    for species, flag, catch, level in sorted(normal, key=lambda x: x[0]):
        if species in TARGETS:
            print(f"  {species} {TARGETS[species]} flag={flag} catch_time={catch} (0x{catch:08x}) level={level}")


asyncio.run(main())