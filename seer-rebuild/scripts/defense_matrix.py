import sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData

d = BattleData(r"F:\seer\seer_cfg\json")
# types[atk][def] = atk 打 def 的倍率
print("=== 各属性【挨】战斗 / 火的倍率（越小越抗打） + 打战斗+火的倍率 ===")
rows = []
for ty in d.types:
    take_fight = d.types["战斗"].get(ty, 1.0) if "战斗" in d.types else 1.0
    take_fire = d.types["火"].get(ty, 1.0) if "火" in d.types else 1.0
    atk_fight = d.types[ty].get("战斗", 1.0)
    atk_fire = d.types[ty].get("火", 1.0)
    # 综合：防御越好 = take 越小；进攻越好 = atk 越大
    take = max(take_fight, take_fire)  # 最差那个
    atk = max(atk_fight, atk_fire)
    rows.append((ty, take_fight, take_fire, atk_fight, atk_fire, take, atk))

print(f"{'类型':4} 挨战斗 挨火  打战斗 打火  | 最差挨  最好打")
for ty, tf, th, af, ah, take, atk in sorted(rows, key=lambda r: (r[5], -r[6])):
    if take <= 1.0 or atk >= 2.0:
        print(f"{ty:4}  {tf:5} {th:5}  {af:5} {ah:5}  |  {take:5}  {atk:5}")