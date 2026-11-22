# -*- coding: utf-8 -*-
"""核对推荐打手的克制倍率：单属性组合 × typesRelation.ini。只读。"""
import sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData

bd = BattleData(r"F:\seer\seer_cfg\json")
types = bd.types  # 攻击属性名 -> 防御属性名 -> 倍率

# 攻击手（单属性名列表）
attackers = {
    "月照星魂": ["光", "飞行"],
    "圣光莫妮卡": ["自然", "圣灵"],
    "希瓦": ["虚空"],
    "至序圣华": ["圣灵", "轮回"],
    "启灵元神": ["神灵"],
    "邪灵主宰·摩哥斯": ["邪灵"],
    "利刃之主鲁斯王": ["水"],
    "加尔鲁特(草潘)": ["草"],
}

bosses = {
    "库坦(B1)": ["战斗", "暗影"],
    "艾莫莉萨(B2)": ["战斗", "龙"],
    "卡威治(B3)": ["水", "神秘"],
    "沙罗摩奥(B4)": ["火", "暗影"],
    "瓦坎(B5)": ["神秘", "战斗"],
}

print("攻击手 → BOSS 倍率（两单属性分别相乘后合计）\n")
for an, atypes in attackers.items():
    parts = []
    for bn, btypes in bosses.items():
        # 双属性：对两个防御单属性各取倍率相乘
        tot = 1.0
        for at in atypes:
            row = types.get(at, {})
            for bt in btypes:
                tot *= row.get(bt, 1.0)
        if tot >= 2.0:
            parts.append(f"{bn}:{tot:g}x")
    print(f"  {an}: " + ("  ".join(parts) if parts else "（无≥2×命中）"))

print("\n== 关键单属性对 BOSS 的倍率（用于补查）==")
for at in ["自然", "圣灵", "虚空", "神灵", "轮回", "邪灵", "水", "草", "光", "飞行", "超能"]:
    row = types.get(at, {})
    hits = []
    for bn, btypes in bosses.items():
        t = 1.0
        for bt in btypes:
            t *= row.get(bt, 1.0)
        if t >= 2.0:
            hits.append(f"{bn}:{t:g}")
    if hits:
        print(f"  {at}: " + "  ".join(hits))