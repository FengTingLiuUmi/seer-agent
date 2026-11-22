# -*- coding: utf-8 -*-
"""瓦坎地狱因子分析：BOSS 类型克制 + 关键技能分类。"""
import sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.battle_data import BattleData, TYPE_NAMES

bd = BattleData(r"F:\seer\seer_cfg\json")

# BOSS species -> type id (双属性 type id 是组合 id，需要从 species.type 拿到组合，但这里
# species.type 是「组合 id」还是「单属性 id」？本地 monsters_pro.ini 的 Type 通常是组合 id。
# 用 typesRelation.ini 的键是中文单属性名，攻守都是单属性；双属性要分开算乘法。
def combo_name(combo_id: int) -> str:
    # 组合 id 在本地没有直接中文名映射，回退到 seerapi；这里只打印 type id
    return str(combo_id)

bosses = {
    4503: "库坦",
    3573: "艾莫莉萨",
    4632: "卡威治",
    4965: "沙罗摩奥",
    4968: "瓦坎",
}

# 双属性类型（用 seerapi 得到的组合，双属性 primary/secondary 单属性 id）
# 战斗=11 暗影=13 龙=15 水=2 神秘=14 火=3 (单属性 id 与 TYPE_NAMES 一致)
boss_dual = {
    4503: ("战斗", "暗影"),
    3573: ("战斗", "龙"),
    4632: ("水", "神秘"),
    4965: ("火", "暗影"),
    4968: ("神秘", "战斗"),
}

def type_chart_row(atk_name: str) -> dict:
    return bd.types.get(atk_name, {})

print("== 本地 typesRelation.ini 键（攻击属性）==")
print(sorted(bd.types.keys()))
print()

for sp, nm in bosses.items():
    sp_obj = bd.species.get(sp)
    line = f"{nm}({sp}) type_id={sp_obj.type if sp_obj else '?'} 双属性={boss_dual[sp]}"
    print(line)
    if sp_obj:
        print("   本地skills:", sp_obj.skills[:8])

print()
print("== 克制表（攻击属性 -> 对 BOSS 单属性的倍率）==")
for atk in sorted(bd.types.keys()):
    row = bd.types[atk]
    # 对每个 boss 计算双倍率（两单属性相乘）
    parts = []
    for sp, nm in bosses.items():
        t1, t2 = boss_dual[sp]
        m = row.get(t1, 1.0) * row.get(t2, 1.0)
        if m >= 2.0:
            parts.append(f"{nm}:{m:g}")
    if parts:
        print(f"  {atk:6s} -> " + "  ".join(parts))

print()
print("== 关键技能分类（1物攻 2特攻 3属性）==")
key_skills = {
    31505: "守御八方(帝皇之御)",
    19314: "剑挥四方(六界)",
    35914: "幻梦芳逝(蒂朵)",
    33309: "月下华尔兹(月照星魂)",
    31253: "时空跃迁术(时空界皇)",
    37140: "叶刃百裂击(加尔鲁特)",
    38655: "瓦坎第五",
}
for sid, nm in key_skills.items():
    m = bd.moves.get(sid)
    if m:
        cat = {1: "物攻", 2: "特攻", 3: "属性"}.get(m.category, str(m.category))
        print(f"  {sid} {nm}: name={m.name} cat={cat} power={m.power} type={TYPE_NAMES.get(m.type,m.type)} prio={m.priority} musthit={m.must_hit}")
    else:
        print(f"  {sid} {nm}: (本地无)")