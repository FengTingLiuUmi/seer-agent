import sys, json
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.roster_cache import load

# 已锁 catch_time（stage1-4 过关占用）
LOCKED = {
    1612845486, 1659858712, 1610423766, 1795108500, 1780054592,   # 帝皇/六界神王/时空界皇/霞冠星礼/希瓦
    1655656403, 1613750784, 1613835444,                            # 蒂朵/六界帝神/月照星魂
    1718386667,                                                    # 加尔鲁特
    1658369845, 1678553578, 1654918859, 1614431841, 1624720755, 1676555665,  # 表姐1/魔钰/龙焉/圣王/御象/表姐2
}

# 对 地面·超能(伊娜) 1.5× 单系 / 2.5× 光·暗影
GOOD = {"草", "水", "冰", "虫", "光", "暗影", "次元", "虚空"}
GOOD_DUAL = {"光·暗影", "暗影·光"}

def types_of(p):
    return set((p.get("type") or "").replace("，", ",").replace("·", " ").split())

pets = load()
print(f"物种总数 {len(pets)}")
rows = []
for p in pets:
    inds = [i for i in (p.get("individuals") or []) if int(i.get("catch_time") or 0) not in LOCKED]
    if not inds:
        continue
    lv = max((int(i.get("level") or 0) for i in inds), default=0)
    if lv < 90:
        continue
    ts = types_of(p)
    eff = ""
    if "光" in ts and "暗影" in ts:
        eff = "2.5×光暗"
    elif ts & GOOD:
        eff = "1.5×" + "/".join(sorted(ts & GOOD))
    else:
        eff = ""
    atk = int(p.get("atk") or 0)
    spa = int(p.get("sp_atk") or 0)
    rows.append((p["species_id"], p["name"], p.get("type"), eff, atk, spa,
                 "、".join(p.get("role_tags") or []), "、".join(p.get("soulmark_tags") or []),
                 [(int(i.get("catch_time") or 0), i.get("level")) for i in inds]))

# 先按是否克制、再按攻击排
rows.sort(key=lambda r: (-(len(r[3]) > 0), -max(r[4], r[5])))
print(f"\n== 未锁且等级>=90 的可出战精灵（按克制优先）==")
for r in rows:
    eff = r[3] or "·"
    print(f"{r[0]:5d} {r[1]:<12s} type={r[2]:<10s} {eff:10s} atk={r[4]:>3d} spa={r[5]:>3d} 定位={r[6]} 魂印={r[7]} 个体={r[8]}")