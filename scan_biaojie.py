import asyncio, struct, sys, json
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.connection import open_unity
from seer_rebuild.commands import Cmd
from seer_rebuild.features import list_body, u32

ACCOUNT = sys.argv[1]
PASSWORD = sys.argv[2]
BIADJIE = [1658369845, 1676555665]  # 帝皇之御(表姐) 两个个体

def parse_2301_skills(body):
    if len(body) < 0x90:
        return []
    return [struct.unpack_from(">I", body, 0x6c + 8*i)[0] for i in range(5)]

async def main():
    c = await open_unity(ACCOUNT, PASSWORD)
    loop = asyncio.get_running_loop()
    # 伊娜进度键 + 锁定键
    await c.send(Cmd.GET_MULTI_FOREVER, [list_body([303274, 303275, 303272])])
    await c.send(Cmd.GET_MULTI_FOREVER, [list_body(list(range(303248, 303272)))])
    for ct in BIADJIE:
        await c.send(Cmd.GET_PET_INFO, [u32(ct)])

    progress = None
    locks = None
    skills = {}
    end = loop.time() + 12.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == Cmd.GET_MULTI_FOREVER:
            from seer_rebuild.factor_runner import parse_forever
            vals = parse_forever(f.body)
            if progress is None:
                progress = vals
            elif locks is None:
                locks = [(303248 + i, v) for i, v in enumerate(vals) if v != 0]
        elif f.cmd == Cmd.GET_PET_INFO:
            skills[len(skills)] = parse_2301_skills(f.body)
    await c.close()
    print(json.dumps({"progress_keys_303274_275_272": progress, "locked_nonzero": locks,
                      "biaojie_skill_slots_in_send_order": skills}, ensure_ascii=False, indent=2))

asyncio.run(main())