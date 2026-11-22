# -*- coding: utf-8 -*-
"""清空当前正式阵容，加入指定精灵并设置首发；读背包回显。写操作。"""
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

def u32(v): return struct.pack(">I", v & 0xFFFFFFFF)

async def send_and_drain(c, cmd, body, timeout=2.0):
    await c.send(cmd, [body] if body else [])
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    recv = []
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(0.7, end-loop.time()))
        except asyncio.TimeoutError:
            continue
        recv.append((f.cmd, f.result))
    return recv

async def main():
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    bd = BattleData(r"F:\seer\seer_cfg\json")
    clear = [1613835444, 1678553578]          # 月照星魂, 魔钰(禁)
    add_formal = [1612845486, 1613750784, 1610423766]  # 表姐A, 六界帝神, 时空界皇
    starter = 1612845486

    c = await open_unity(u, s, timeout=25.0)
    out = []
    for ct in clear:
        await send_and_drain(c, Cmd.PET_RELEASE, u32(ct)+u32(0))
        out.append(f"clear {ct}")
    for ct in add_formal:
        await send_and_drain(c, Cmd.PET_RELEASE, u32(ct)+u32(1))
        out.append(f"add formal {ct}")
    await send_and_drain(c, Cmd.PET_DEFAULT, u32(starter))
    out.append(f"starter {starter}")

    # 读背包验证
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
            formal = pets[:cnt]; reserve = pets[cnt:]
            break
    await c.close()
    nm = lambda p: (bd.species.get(p.species_id).name if bd.species.get(p.species_id) else str(p.species_id))
    print(json.dumps({
        "steps": out,
        "正式": [{"name": nm(p), "species_id": p.species_id, "catch_time": p.catch_time} for p in formal],
        "待命": [{"name": nm(p), "species_id": p.species_id, "catch_time": p.catch_time} for p in reserve],
    }, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())