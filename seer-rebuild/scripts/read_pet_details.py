"""读关键打手个体的 2301 详情（等级 + 装备技能），供组队用。只读。"""
import asyncio, json, os, struct, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PYTHONIOENCODING"] = "utf-8"

from seer_rebuild.connection import open_unity
from seer_rebuild.pet_details import parse_2301


def vault(name):
    import subprocess
    p = subprocess.run(["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                                             "dsh-credential-vault", "vaultctl.mjs"), "show", name],
                       capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))


def local_names():
    names_sp = {}
    names_sk = {}
    try:
        from seer_rebuild.battle_data import BattleData
        bd = BattleData(r"F:\seer\seer_cfg\json")
        names_sp = {sp: s.name for sp, s in bd.species.items()}
        names_sk = {sid: m.name for sid, m in bd.moves.items()}
    except Exception:
        pass
    return names_sp, names_sk


TARGETS = [
    ("帝皇之御", 0x62D8B735),
    ("帝皇之御", 0x63EE3591),
    ("帝皇之御", 0x602211AE),
    ("六界神王", 0x62EF6F18),
    ("六界帝神", 0x602FE200),
    ("时空界皇", 0x5FFD1DD6),
    ("希瓦", 0x6A197A40),
    ("蒂朵", 0x62AF4FD3),
    ("圣灵谱尼", 0x57C55A7F),
    ("月照星魂", 0x60312CB4),
    ("弑序神罗", 0x5FF913DE),
    ("魔钰", 0x640CB1EA),
    ("艾欧丽娅", 0x5FF9227D),
    ("王之哈莫", 0x57B67917),
]


async def main():
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    names_sp, names_sk = local_names()
    c = await open_unity(u, s, timeout=25.0)
    loop = asyncio.get_running_loop()

    for label, ct in TARGETS:
        await c.send(2301, [struct.pack(">I", ct & 0xFFFFFFFF)])
        body = b""
        end = loop.time() + 6.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=0.8)
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2301 and len(f.body) >= 0x80:
                body = f.body
                break
        if not body:
            print(f"{label} ct=0x{ct:08X}: (无 2301 回包)")
            continue
        d = parse_2301(body)
        sk = ", ".join(f"{sid}({names_sk.get(sid, '?')})" for sid in d.skills)
        sp_name = names_sp.get(d.species_id, d.species_id)
        print(f"{label} ct=0x{ct:08X}: species={d.species_id}({sp_name}) lv={d.level} "
              f"HP={d.cur_hp}/{d.max_hp} 物攻={d.atk} 特攻={d.sp_atk} 速度={d.spd} 技能={sk}")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())