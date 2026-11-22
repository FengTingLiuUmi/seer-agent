import json, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData

bd = BattleData(r"F:\seer\seer_cfg\json")

# 候选精灵的未锁个体 catch_time
CAND = {
    4906: [1780052570],   # 阿西列维 光·暗影 2.5×
    4913: [1781288880],   # 夏哆 光·暗影 2.5×
    4169: [1610159070],   # 弑序神罗 虚空·混沌 固定/百分比
    4189: [1614397150],   # 凌雪·樱 混沌·冰
    3924: [1613751950],   # 凛戾·寂灭魔神 电·冰
    4880: [1780052552],   # 洛欧蒂 光·战斗
    4458: [1675263576],   # 业凛 混沌·冰
    3699: [1611592315],   # 冰之契约·阿克希亚 冰
    5000: [1472551551],   # 圣灵谱尼(31143 禁回血)
}

dyn = json.load(open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\data\roster_cache.json", encoding="utf-8"))
print("== candidate equipped skills ==")
for sp, cts in CAND.items():
    name = bd.species.get(sp).name if bd.species.get(sp) else str(sp)
    indivs = dyn.get(str(sp), [])
    for ct in cts:
        hit = next((i for i in indivs if int(i.get("catch_time") or 0) == ct), None)
        sids = (hit or {}).get("skills") or []
        details = []
        for sid in sids:
            m = bd.moves.get(sid)
            nm = m.name if m else "?"
            pwr = getattr(m, "power", "?") if m else "?"
            el = getattr(m, "element", "?") if m else "?"
            details.append(f"{sid}({nm},威力{pwr},{el})")
        print(f"{sp} {name} ct={ct} lv={(hit or {}).get('level')}:")
        for d in details:
            print(f"    {d}")