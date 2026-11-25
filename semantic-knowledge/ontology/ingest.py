# -*- coding: utf-8 -*-
"""
ingest.py v0.2 —— 从 SeerAPI 拉数据，按 seer-game.ttl 的 TBox 生成 ABox。
用法：
    python ingest.py --limit 10    # 每类资源只取前 10 条（快速验证）
    python ingest.py --full        # 全量（耗时长）
输出：<脚本目录>/seer-game-abox.ttl
依赖：rdflib（PYTHONPATH 指向 .pylibs 或已全局安装）

注意：SeerAPI 的 list 只返回 {id,url} 摘要，get 返回完整对象；故用“list 取 id → get 取全量”。
"""
import json, os, sys, time, urllib.request
from rdflib import Graph, Namespace, RDF, RDFS, Literal, XSD

BASE = "https://api.seerapi.com/v1/"
SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))

g = Graph()
g.bind("seer", SEER)
_cache = {}
_stats = {}

# 常用 PVE 精灵库（已核对的规范实体 id；消歧见 seer-pve-alias.ttl）
PVE_IDS = [4344, 4648, 4649, 4647, 3437, 3512, 3329, 3463, 4377,
           5000, 12, 3594, 4463, 2933, 3567, 4484, 4636, 3390, 3516, 3060, 3022,
           3460, 3322, 3613, 4487, 4442, 4606, 3414, 3986, 3291,
           3866, 3711, 4732, 3517, 3561, 4628, 4462, 3894, 3141, 4871, 3926,
           3118, 2735, 3540, 3031, 4721, 2499, 3438, 4912, 4146, 3844, 4797,
           3406, 4223, 3938, 3194, 3221, 2977, 3443, 2807, 3239, 4321]

PET_SKILLS = []  # (pet_iri, [skill_ref,...])，待 ingest_skills() 判定有效技能


def get_json(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seer-ingest/0.2"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(0.5)


def list_ids(resource, limit=None):
    """list 端点只回 {id,url}；这里只收集 id。"""
    ids, url = [], f"{BASE}{resource}?limit=100"
    while url:
        data = get_json(url)
        if not data:
            break
        for it in data.get("results", []):
            if it.get("id") is not None:
                ids.append(it["id"])
                if limit is not None and len(ids) >= limit:
                    return ids
        if limit is not None and len(ids) >= limit:
            return ids
        url = data.get("next")
    return ids


def get_item(resource, rid):
    key = (resource, str(rid))
    if key not in _cache:
        _cache[key] = get_json(f"{BASE}{resource}/{rid}")
    return _cache[key]


def bump(cls):
    _stats[cls] = _stats.get(cls, 0) + 1


def add_label(s, name):
    if name:
        g.add((s, RDFS.label, Literal(str(name), lang="zh")))


def raw(v):
    return Literal(json.dumps(v, ensure_ascii=False)) if v is not None else None


def boss_flag(text):
    t = (text or "").lower()
    if "boss有效" in t:
        return True
    if "boss无效" in t:
        return False
    return None


# ---------------------------------------------------------------------------
# 各资源映射（入参为 get 返回的完整对象）
# ---------------------------------------------------------------------------
def map_pet(p):
    pid = p.get("id")
    s = SEER[f"pet_{pid}"]
    g.add((s, RDF.type, SEER.Pet))
    g.add((s, SEER.seerapiId, Literal(str(pid))))
    add_label(s, p.get("name"))
    bs = p.get("base_stats") or {}
    for k, prop in [("hp", "baseHp"), ("atk", "baseAtk"), ("def", "baseDef"),
                    ("sp_atk", "baseSpAtk"), ("sp_def", "baseSpDef"), ("spd", "baseSpd"),
                    ("total", "total")]:
        v = bs.get(k)
        if v is not None:
            g.add((s, SEER[prop], Literal(int(v))))
    t = p.get("type") or {}
    if t.get("id"):
        g.add((s, SEER.hasTypeCombination, SEER[f"tc_{t['id']}"]))
    PET_SKILLS.append((s, p.get("skill") or []))
    for sm in p.get("soulmark") or []:
        smid = sm.get("id")
        if smid:
            g.add((s, SEER.hasSoulmark, SEER[f"soulmark_{smid}"]))
    for fac in p.get("factor") or []:
        fid = fac.get("id")
        if fid:
            g.add((s, SEER.appearsInFactor, SEER[f"factor_{fid}"]))
    bump("Pet")


def map_skill(sk):
    sid = sk.get("id")
    s = SEER[f"skill_{sid}"]
    g.add((s, RDF.type, SEER.Skill))
    g.add((s, SEER.seerapiId, Literal(str(sid))))
    add_label(s, sk.get("name"))
    for k in ("power", "priority"):
        v = sk.get(k)
        if v is not None:
            g.add((s, SEER[k], Literal(int(v))))
    # 技能属性（攻击方克制按此，而非精灵属性）
    t = sk.get("type") or {}
    if t.get("id") is not None:
        g.add((s, SEER.skillType, SEER[f"tc_{t['id']}"]))
    # 技能效果实例 + 是否 boss 有效
    for i, e in enumerate(sk.get("skill_effect") or []):
        if not isinstance(e, dict):
            continue
        be = SEER[f"skillfx_{sid}_{i}"]
        g.add((be, RDF.type, SEER.SkillEffect))
        g.add((s, SEER.hasSkillEffect, be))
        et = (e.get("effect") or {}).get("id")
        if et is not None:
            st = SEER[f"setype_{et}"]
            g.add((st, RDF.type, SEER.SkillEffectType))
            g.add((st, SEER.seerapiId, Literal(str(et))))
            g.add((be, SEER.effectTypeOf, st))
        if e.get("args"):
            g.add((be, SEER.effectArgs, raw(e["args"])))
        if e.get("info"):
            g.add((be, SEER.effectInfo, Literal(str(e["info"]))))
        bf = boss_flag(" ".join(str(x) for x in [e.get("analyze_info"), e.get("info")] if x))
        if bf is not None:
            g.add((be, SEER.bossEffective, Literal(bf, datatype=XSD.boolean)))
    bump("Skill")


def map_soulmark(sm):
    sid = sm.get("id")
    s = SEER[f"soulmark_{sid}"]
    g.add((s, RDF.type, SEER.Soulmark))
    g.add((s, SEER.seerapiId, Literal(str(sid))))
    eff = sm.get("effect") or {}
    eid = (eff.get("effect") or {}).get("id")
    if eid:
        g.add((s, SEER.grantsEffect, SEER[f"eid_{eid}"]))
        g.add((SEER[f"eid_{eid}"], RDF.type, SEER.EidEffect))
        g.add((SEER[f"eid_{eid}"], SEER.seerapiId, Literal(str(eid))))
    pv = sm.get("pve_effective")
    if pv is not None:
        g.add((s, SEER.pveEffective, Literal(bool(pv), datatype=XSD.boolean)))
    bump("Soulmark")


def map_tc(tc):
    tid = tc.get("id")
    s = SEER[f"tc_{tid}"]
    g.add((s, RDF.type, SEER.TypeCombination))
    g.add((s, SEER.seerapiId, Literal(str(tid))))
    add_label(s, tc.get("name"))
    bump("TypeCombination")


def map_named(resource, cls, extra=None, item_limit=None):
    for rid in list_ids(resource, limit=item_limit):
        it = get_item(resource, rid)
        if not it:
            continue
        s = SEER[f"{resource}_{rid}"]
        g.add((s, RDF.type, SEER[cls]))
        g.add((s, SEER.seerapiId, Literal(str(rid))))
        add_label(s, it.get("name"))
        if extra:
            extra(s, it)
        bump(cls)


def ingest_pets(ids):
    for pid in ids:
        p = get_item("pet", pid)
        if p:
            map_pet(p)


def ingest_skills():
    """入库精灵的全部技能（不做"只留先制/属性技"的过滤）。

    早期版本会丢掉 先制<=0 且 非属性技 的技能，导致战斗决策时连普攻都查不到；
    战斗里 4 个技能位什么都可能上，所以必须全留。体量可控：只有已入库精灵的技能。
    """
    kept = set()
    for s, skills in PET_SKILLS:
        for sk in skills:
            sid = (sk.get("skill") or {}).get("id")
            if not sid:
                continue
            kept.add(sid)
            g.add((s, SEER.hasSkill, SEER[f"skill_{sid}"]))
    for sid in kept:
        so = get_item("skill", sid)
        if so:
            map_skill(so)


def ingest_referenced():
    need_soul = {str(o).rsplit("#", 1)[-1][9:] for o in g.objects(None, SEER.hasSoulmark)}
    need_tc = {str(o).rsplit("#", 1)[-1][3:] for o in g.objects(None, SEER.hasTypeCombination)}
    for smid in need_soul:
        sm = get_item("soulmark", smid)
        if sm:
            map_soulmark(sm)
    for tid in need_tc:
        tc = get_item("element_type_combination", tid)
        if tc:
            map_tc(tc)


def ingest_named(limit):
    def mint_extra(s, it):
        for k, prop in [("base_attr_value", "baseAttrValue"), ("extra_attr_value", "extraAttrValue"),
                        ("max_attr_value", "maxAttrValue")]:
            v = raw(it.get(k))
            if v is not None:
                g.add((s, SEER[prop], v))
    # Suit / Title / Nature 的唯一写者是 ingest_gear.py（它的 seer-gear-abox.ttl 走详情接口，
    # 能拿到 name；本脚本的 list 接口拿不到 name，若在此处再写会与 gear abox 产生双 label）。
    map_named("mintmark", "Mintmark", mint_extra, limit)


def main(limit, full, pve=False):
    if pve:
        print("ingest: 常用 PVE 精灵库", len(PVE_IDS), "只")
        ingest_pets(PVE_IDS)
        ingest_skills()
        ingest_referenced()
    else:
        print("ingest:", "全量" if full else f"前 {limit} 条/资源")
        ingest_pets(list_ids("pet", limit=None if full else limit))
        ingest_skills()
        ingest_referenced()
        ingest_named(None if full else limit)

    out = os.path.join(HERE, "seer-pve-abox.ttl" if pve else "seer-game-abox.ttl")
    g.serialize(destination=out, format="turtle")
    print("完成 ->", out, "\n三元组 =", len(g))
    for k, v in sorted(_stats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--pve" in args:
        main(None, False, True)
    elif "--full" in args:
        main(None, True, False)
    elif "--limit" in args:
        main(int(args[args.index("--limit") + 1]), False, False)
    else:
        main(10, False, False)