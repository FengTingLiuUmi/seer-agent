import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
for sid in [377, 365, 389]:
    d = p.get("suit", sid)
    equips = [(e.get("id")) for e in (d or {}).get("equips") or []]
    print(f"suit {sid} {d.get('name')} equips={equips} bonus={d.get('bonus')}")

# 当前装备是什么（从抓包里的 0013d8be 等）
print("\n当前 2604 装备件（抓包）:")
for eid in [0x13D8BE, 0x13D8BF, 0x13D8C0, 0x13D8C1, 0x13D9DA]:
    eq = p.get("equip", eid)
    nm = (eq or {}).get("name") if eq else None
    print(f"  {eid} -> {nm}")