import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()


def find(res, name, limit=6):
    r = p._run("list", res, "--name", name, "--limit", str(limit))
    out = r.get("results") if isinstance(r, dict) else r
    return out or []


# 查经典 PVE 套装
for kw in ["银翼", "皇帝", "天尊", "山神", "天启", "减伤", "先制", "攻击", "御象"]:
    for d in find("suit", kw):
        bonus = d.get("bonus") or {}
        bdesc = bonus.get("desc") if isinstance(bonus, dict) else None
        print(f"[suit] {d.get('id')} {d.get('name')} bonus={bdesc}")


def get_title(tid):
    d = p.get("title", tid)
    return d


print("\n=== 当前账号称号 236 ===")
t = get_title(236)
print(t)

# 查加攻击/体力/先制/能力的称号
for kw in ["攻击", "体力", "先制", "速度", "能力", "至尊"]:
    for d in find("title", kw):
        ab = d.get("attr_bonus")
        ad = d.get("ability_desc")
        if ab or d.get("is_ability_bonus") or ad:
            print(f"[title] {d.get('id')} {d.get('name')} attr_bonus={ab} ability={ad} is_ability={d.get('is_ability_bonus')}")