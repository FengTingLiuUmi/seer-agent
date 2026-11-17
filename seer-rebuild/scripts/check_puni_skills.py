import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
for sid in [31140, 31141, 25678, 25679, 31143]:
    sd = p.get("skill", sid, fields=["id", "name", "power", "type", "priority", "skill_effect"])
    effs = [e.get("info") for e in ((sd or {}).get("skill_effect") or [])]
    print(f"\n{sid} {(sd or {}).get('name')} power={(sd or {}).get('power')} 先制={(sd or {}).get('priority')}")
    for e in effs:
        print(f"  效果: {e}")