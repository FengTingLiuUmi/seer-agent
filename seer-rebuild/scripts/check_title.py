import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()

# 之前回包里见过的两个称号 id
for tid in [236, 272]:
    d = p.get("title", tid)
    print(f"\n=== title {tid} {d.get('name') if d else '?'} ===")
    print("  attr_bonus:", d.get("attr_bonus"))
    print("  is_ability_bonus:", d.get("is_ability_bonus"))
    print("  ability_desc:", d.get("ability_desc"))
    print("  desc:", d.get("desc"))

# 搜「属性/能力」相关称号（is_ability_bonus=True 的）
print("\n=== 搜含 属性/水/超能/战斗 的称号（is_ability_bonus）===")
for kw in ["属性", "水", "超能", "战斗", "火", "地面"]:
    r = p._run("list", "title", "--name", kw, "--limit", "8")
    for d in (r.get("results") or []) if isinstance(r, dict) else []:
        if d.get("is_ability_bonus") or d.get("ability_desc"):
            print(f"  [{d.get('id')}] {d.get('name')} attr={d.get('attr_bonus')} ability={d.get('ability_desc')}")