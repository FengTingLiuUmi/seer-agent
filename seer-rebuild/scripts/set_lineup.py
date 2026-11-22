# -*- coding: utf-8 -*-
"""通用阵容设置：清正式 + 加正式(按序=首发队列) + 设首发。argv: clear csv | add csv | starter。
只发 2304/2308，最后读 43706 回显。"""
import asyncio, json, os, struct, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
os.environ["PYTHONIOENCODING"] = "utf-8"
from seer_rebuild.connection import open_unity
from seer_rebuild.commands import Cmd
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData

def vault(name):
    import subprocess
    p = subprocess.run(["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                       "dsh-credential-vault", "vaultctl.mjs"), "show", name], capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))

def parse_csv(txt):
    if not txt or txt.strip() in ("", "-", "none"):
        return []
    return [int(x, 0) for x in txt.split(",") if x.strip()]

def u32(v): return struct.pack(">I", v & 0xFFFFFFFF)

async def drain(c, cmd, body, timeout=1.6):
    await c.send(cmd, [body] if body else [])
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end-loop.time()))
        except asyncio.TimeoutError:
            continue

async def main():
    clear = parse_csv(sys.argv[1]); add = parse_csv(sys.argv[2]); starter = int(sys.argv[3], 0) if len(sys.argv) > 3 and sys.argv[3] not in ("", "0", "-") else None
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    bd = BattleData(r"F:\seer\seer_cfg\json")
    c = await open_unity(u, s, timeout=25.0)
    for ct in clear:
        await drain(c, Cmd.PET_RELEASE, u32(ct)+u32(0))
    for ct in add:
        await drain(c, Cmd.PET_RELEASE, u32(ct)+u32(1))
    if starter:
        await drain(c, Cmd.PET_DEFAULT, u32(starter))
    await c.send(Cmd.GET_PET_INFO_BY_ONCE, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 8.0
    formal, reserve = [], []
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end-loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == Cmd.GET_PET_INFO_BY_ONCE:
            cnt, pets = parse_bag_43706(f.body, data=bd)
            formal = pets[:cnt]; reserve = pets[cnt:]; break
    await c.close()
    nm = lambda p: (bd.species.get(p.species_id).name if bd.species.get(p.species_id) else str(p.species_id))
    print(json.dumps({
        "正式": [{"name": nm(p), "species_id": p.species_id, "catch_time": p.catch_time} for p in formal],
        "待命": [{"name": nm(p), "species_id": p.species_id, "catch_time": p.catch_time} for p in reserve],
    }, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())