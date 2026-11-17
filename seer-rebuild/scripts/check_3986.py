import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


d = p.get("pet", 3986, fields=["id", "name", "type", "soulmark"])
t = (d.get("type") or {}).get("id")
print(f"=== {d.get('id')} {d.get('name')} [{combo(t)}] ===")
for sm in (d.get("soulmark") or []):
    smd = p.get("soulmark", sm["id"], fields=["id", "name", "desc"]) if sm.get("id") else None
    if smd:
        print("魂印:", smd.get("name"), "->", smd.get("desc"))

print("\n=== 技能（全部）===")
for skd in (d.get("skill") or []):
    skid = (skd.get("skill") or {}).get("id")
    if skid:
        sd = p.get("skill", skid, fields=["id", "name", "power", "category", "type", "priority", "skill_effect"])
        st = (sd or {}).get("type") or {}
        effs = [e.get("info") for e in ((sd or {}).get("skill_effect") or [])]
        print(f"  {skid} {(sd or {}).get('name')} power={(sd or {}).get('power')} 类型={combo(st.get('id')) if st else '?'} 先制={(sd or {}).get('priority')}")
        for e in effs:
            print(f"      效果: {e}")