import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()


def et(tid):
    d = p.get("equip_type", tid)
    return (d or {}).get("name") or str(tid)


# 银翼 4件 + 皇帝 4件 + 目镜候选
ids = [1300670, 1300671, 1300672, 1300673, 1300724, 1300725, 1300726, 1300727, 1301040, 1300954]
for eid in ids:
    d = p.get("equip", eid)
    nm = (d or {}).get("name") if d else None
    tt = (d or {}).get("equip_type") if d else None
    ttid = tt.get("id") if isinstance(tt, dict) else tt
    print(f"{eid}  {nm}  equip_type={ttid} {et(ttid) if ttid else ''}")