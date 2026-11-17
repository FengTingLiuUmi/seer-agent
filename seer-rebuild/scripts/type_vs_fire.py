import sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData

d = BattleData(r"F:\seer\seer_cfg\json")
print("=== 各种攻击属性 vs 战斗 / 火 ===")
for atk in ["超能", "虚空", "混沌", "飞行", "水", "地面", "冰", "火", "战斗", "光", "暗影", "神秘", "虫", "圣灵", "自然", "远古", "王", "轮回"]:
    if atk in d.types:
        vs_f = d.types[atk].get("战斗", 1.0)
        vs_h = d.types[atk].get("火", 1.0)
        prod = vs_f * vs_h
        print(f"{atk:3s} vs战斗={vs_f} vs火={vs_h} 积={prod}")