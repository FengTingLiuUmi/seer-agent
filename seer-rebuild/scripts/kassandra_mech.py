"""查卡杉德拉(3599)魂印 + 技能31966/31962/31964/31967 效果，搞清单精灵关怎么打。"""
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


d = p.get("pet", 3599, fields=["id", "name", "type", "soulmark", "base_stats", "peak_pool", "peak_expert_pool"])
print("卡杉德拉 3599 基本信息:")
print("  name:", d.get("name"), "type:", combo((d.get("type") or {}).get("id")))
print("  peak_pool:", d.get("peak_pool"))
print("  base_stats:", d.get("base_stats"))
print("\n=== 魂印 soulmark ===")
for sm in (d.get("soulmark") or []):
    sid = sm.get("id")
    smd = p.get("soulmark", sid, fields=["id", "name", "desc"]) if sid else None
    print(" ", sid, "->", smd)

print("\n=== 关键技能 ===")
for sid in [31962, 31963, 31964, 31965, 31966, 31967]:
    sd = p.get("skill", sid, fields=["id", "name", "power", "category", "type", "priority", "skill_effect"])
    t = (sd or {}).get("type") or {}
    effs = [e.get("info") for e in ((sd or {}).get("skill_effect") or [])]
    print(f"  {sid} {(sd or {}).get('name')} power={(sd or {}).get('power')} 类型={combo(t.get('id')) if t else '?'} 先制={(sd or {}).get('priority')}")
    for e in effs[:6]:
        print(f"      效果: {e}")