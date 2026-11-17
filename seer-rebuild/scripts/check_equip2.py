"""查 5 件装备的部位与加成。"""
from seer_rebuild.provider import SeerApiProvider

EQUIP_TYPE = {0: "头部", 1: "目镜", 2: "腰部", 3: "手部", 4: "足部", 5: "背景", 6: "坐骑"}

ids = [0x13DA30, 0x13DA36, 0x13DA34, 0x13DA33, 0x13DA35]  # 漫游者-AH、漆黑4件
names = ["漫游者-AH", "漆黑之刺", "漆黑之正义", "漆黑之假面", "漆黑之缚"]

p = SeerApiProvider()
for i, (obj_id, expected) in enumerate(zip(ids, names), 1):
    d = p.get("equip", obj_id)
    if not d:
        print(obj_id, expected, "<no equip>")
        continue
    pt = (d.get("part_type") or {}).get("id")
    slot = EQUIP_TYPE.get(int(pt), f"part{pt}")
    bonus = ""
    if d.get("bonus") and d["bonus"].get("desc"):
        bonus = d["bonus"]["desc"]
    suit = (d.get("suit") or {}).get("id")
    print(f"{i}. [{slot}] {d.get('name')}  (id={obj_id})  bonus={bonus or '无'}  suit={suit}")