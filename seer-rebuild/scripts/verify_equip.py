import json

from seer_rebuild.inventory import _worn_sections, snapshot_from_live, resolve
from seer_rebuild.provider import SeerApiProvider

# 1) 用已有抓到的 1001 验证分段
for fn in ("seer-rebuild/pets_raw2.jsonl", "seer-rebuild/pets_raw.jsonl"):
    for l in open(fn, encoding="utf-8"):
        d = json.loads(l)
        if d["cmd"] == 1001:
            c, e = _worn_sections(bytes.fromhex(d["body"]))
            print(f"[{fn}] 装扮:", [hex(x) for x in c], "装备:", [hex(x) for x in e])
            break

# 2) 实时读 + 反查
snap = snapshot_from_live("ACCOUNT", "PASSWORD", None)
resolve(snap, SeerApiProvider())
print("\n=== 装备（头盔/护甲/武器/目镜）===")
for i in snap.equipment:
    b = i.bonus or "无"
    sb = i.suit_bonus or "无"
    print(f"  {i.slot}  {i.name}  单件:{b}  套装[{i.suit}]:{sb}")
print("=== 装扮（时装外观）===")
for i in snap.clothes:
    print(f"  {i.slot}  {i.name}")