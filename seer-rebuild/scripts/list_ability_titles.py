import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()

# 分页拉全部 title，找 is_ability_bonus=True 的（属性/能力加成称号）
abl = []
offset = 0
while True:
    r = p._run("list", "title", "--offset", str(offset), "--limit", "100")
    results = r.get("results") or []
    if not results:
        break
    for d in results:
        if d.get("is_ability_bonus"):
            ab = d.get("attr_bonus") or {}
            abl.append((d.get("id"), d.get("name"), d.get("ability_desc"), ab))
    nxt = r.get("next")
    if not nxt:
        break
    offset = nxt.get("offset", offset + 100)

print(f"seerapi 里 is_ability_bonus=True 的称号共 {len(abl)} 个：")
for tid, name, desc, ab in sorted(abl):
    print(f"  {tid}  {name}  [{desc}] atk={ab.get('atk')} spa={ab.get('sp_atk')} hp={ab.get('hp')} def={ab.get('def_')} spd={ab.get('spd')}")