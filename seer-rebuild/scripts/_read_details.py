import asyncio, os, struct
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pet_details import parse_2301

TARGETS = [(0x62D8B735, "帝皇之御"), (0x62EF6F18, "六界神王"), (0x6A13B460, "希瓦")]


async def main():
    sess = authenticate(os.environ["SEER_ACCOUNT"], os.environ["SEER_PASSWORD"])
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    for ct, label in TARGETS:
        f = await c.request(2301, [struct.pack(">I", ct)], timeout=6.0)
        d = parse_2301(f.body)
        print(f"{label} ct=0x{ct:08x} species={d.species_id} level={d.level} "
              f"cur_hp={d.cur_hp} max_hp={d.max_hp} atk={d.atk} sp_atk={d.sp_atk} spd={d.spd} "
              f"skills={d.skills}")
    await c.close()


asyncio.run(main())