import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
for eid in [1301040, 1300954, 1300670]:
    d = p.get("equip", eid)
    print(f"\n=== {eid} {d.get('name') if d else '?'} ===")
    print("  bonus:", d.get("bonus") if d else None)
    print("  effective_occasion:", d.get("equip_effective_occasion") if d else None)