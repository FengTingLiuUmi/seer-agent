import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


for sid in [3033, 2727, 3409]:
    d = p.get("pet", sid, fields=["id", "name", "type", "soulmark"])
    t = (d.get("type") or {}).get("id")
    print(f"\n=== {sid} {d.get('name')} [{combo(t)}] ===")
    for sm in (d.get("soulmark") or []):
        smd = p.get("soulmark", sm["id"], fields=["id", "name", "desc"]) if sm.get("id") else None
        if smd:
            print("  魂印:", smd.get("name"), "->", smd.get("desc"))
    # skills
    for skd in (d.get("skill") or []):
        skid = (skd.get("skill") or {}).get("id")
        if skid:
            sd = p.get("skill", skid, fields=["id", "name", "power", "type", "priority"])
            st = (sd or {}).get("type") or {}
            pw = (sd or {}).get("power")
            if pw and pw >= 100:
                print(f"    技能 {skid} {(sd or {}).get('name')} power={pw} 类型={combo(st.get('id')) if st else '?'} 先制={(sd or {}).get('priority')}")