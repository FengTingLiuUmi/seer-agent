import json, os
root = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\data"
static = json.load(open(os.path.join(root, "account_pets.json"), encoding="utf-8"))
dyn = json.load(open(os.path.join(root, "roster_cache.json"), encoding="utf-8"))
targets = {3865: "希瓦", 3045: "六界神王", 3512: "帝皇之御", 3463: "时空界皇",
           3866: "月照星魂", 3567: "魔钰", 4377: "蒂朵", 3329: "六界帝神",
           4169: "弑序神罗", 4911: "星光艾欧丽娅", 3022: "王之哈莫", 5000: "圣灵谱尼"}
st = {p["species_id"]: p for p in static}
for sid, nm in sorted(targets.items()):
    p = st.get(sid)
    if not p:
        print(f"{sid} {nm}: <不在静态缓存>")
        continue
    inds = dyn.get(str(sid), [])
    print(f"{sid} {nm} | type={p.get('type')} | locs={p.get('locs')} | "
          f"个体={[(i.get('catch_time'), i.get('level'), i.get('skills')) for i in inds]}")