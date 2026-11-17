import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


for sid in [36613, 36614, 26091, 26090, 26092]:
    sd = p.get("skill", sid, fields=["id", "name", "power", "category", "type", "priority", "skill_effect"])
    st = (sd or {}).get("type") or {}
    effs = [e.get("info") for e in ((sd or {}).get("skill_effect") or [])]
    print(f"\n{sid} {(sd or {}).get('name')} power={(sd or {}).get('power')} 类型={combo(st.get('id')) if st else '?'} 先制={(sd or {}).get('priority')}")
    for e in effs:
        print(f"  效果: {e}")