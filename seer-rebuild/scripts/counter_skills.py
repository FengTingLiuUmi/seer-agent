"""查候选超能宠的最强超能系输出招式。"""
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()

def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)

def analyze(species):
    d = p.get("pet", species, fields=["id", "name", "type", "skill"])
    t = (d.get("type") or {}).get("id")
    print(f"\n=== {species} {d.get('name')} [{combo(t)}] ===")
    for sk in d.get("skill") or []:
        sid = (sk.get("skill") or {}).get("id")
        if not sid:
            continue
        sd = p.get("skill", sid, fields=["id", "name", "power", "category", "type", "priority"])
        if not sd:
            print(f"  skill {sid}: ???")
            continue
        st = (sd.get("type") or {}).get("id")
        cat = (sd.get("category") or {}).get("id") if isinstance(sd.get("category"), dict) else sd.get("category")
        print(f"  {sid:6d} {sd.get('name')} power={sd.get('power')} 类型={combo(st) if st else '?'} 先制={sd.get('priority')}")


for s in [3567, 3465, 3507, 4329]:
    analyze(s)