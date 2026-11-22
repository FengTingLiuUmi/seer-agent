# -*- coding: utf-8 -*-
"""离线：从 main_full_dump 提取关键 PVE 精灵的 catch_time，并列 moves（monsters_pro.ini）。"""
import json, sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData, TYPE_NAMES

dump = json.loads((Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\data\main_full_dump.json").read_bytes()).decode("utf-16"))
bd = BattleData(r"F:\seer\seer_cfg\json")

def find(sp):
    out = []
    for g, key in (("bag", "bag"), ("elite", "elite"), ("normal", "normal")):
        for r in dump.get(key, []):
            if r["species_id"] == sp:
                out.append((key, r.get("catch_time"), r.get("flag"), r.get("level")))
    return out

KEY = {
    3512: "帝皇之御(表姐)", 3866: "月照星魂", 3329: "六界帝神", 3045: "六界神王",
    3711: "圣光莫妮卡(圣莫)", 4377: "蒂朵", 4606: "加尔鲁特(草潘)", 3894: "千裳",
    4732: "闪光皮神(闪皮)", 5000: "圣灵谱尼(圣谱)", 2977: "神寂·克罗诺斯(克罗)",
    4463: "斯克鲁恩(冰潘)", 3118: "索比斯", 4648: "星光·鲁斯王", 2947: "利刃之主鲁斯王",
    4649: "星光·魔焰猩猩", 4647: "星光·丽莎布布", 4677: "星辰万象·天启星魂", 3865: "希瓦",
    2933: "泰坦", 4636: "西塔伦", 4797: "极渊DS-001", 3844: "伊芙莉莎", 4321: "至序圣华",
    3561: "邪灵主宰·摩哥斯", 3986: "启灵元神", 2987: "重生之翼", 2735: "天河神将",
    3519: "沙悟净", 3409: "三藏", 2727: "蒙奇多克", 3567: "魔钰(禁)",
}

for sp in sorted(KEY):
    name = KEY[sp]
    inds = find(sp)
    sp_obj = bd.species.get(sp)
    moves = sp_obj.skills if sp_obj else []
    print(f"\n===== {name} (species={sp}) =====")
    print("  个体:", inds)
    print("  moves:")
    for m in moves:
        mo = bd.moves.get(m)
        if mo:
            cat = {1:"物",2:"特",3:"属"}.get(mo.category,"?")
            print(f"    {mo.id} {mo.name} [{cat}] p={mo.power} type={TYPE_NAMES.get(mo.type,mo.type)} prio={mo.priority} hit={mo.must_hit}")
        else:
            print(f"    {m} (无数据)")