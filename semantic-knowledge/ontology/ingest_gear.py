# -*- coding: utf-8 -*-
"""ingest_gear.py v0.2 —— 配装 ABox：suit(套装) / equip(玩家装备部件) / title(称号) / nature(性格) / fire(火，手工)。

v0.1 的 bug：SeerAPI 的 list 接口只回 {id,url}（不含 name/desc），v0.1 直接读 list 的 name →
481 Suit + 597 Title + 25 Nature 的 label 全写成了 "None"。v0.2 一律 "list 取 id → get 取详情"。

数据源（全部实测过字段，schema 见 https://api.seerapi.com/v1/schemas/<res>/$id）：
  /v1/suit?limit=100            -> 481 套装 id
  /v1/suit/{id}                 -> name/suit_desc/transform/tran_speed/equips[]/bonus
  /v1/equip?limit=100           -> 2132 部件 id
  /v1/equip/{id}                -> name/speed/x_position/y_position/item/bonus/occasion/suit/part_type/pk_attribute
  /v1/equip_type/{0..6}         -> 部位枚举 name(head/eye/waist/hand/foot/bg/mount) + 该部位的 equip 列表
  /v1/equip_effective_occasion/{0..2} -> 场合枚举 description(全部战斗有效/仅赛尔间对战有效/仅对Boss有效)
  /v1/title/{id}                -> name/desc/attr_bonus
  /v1/nature/{id}               -> name/des/des2/attributes

语义要点（别搞错，官方原文）：
  * pk_attribute = 战队保卫战等老玩法的 PK 加成，**不是 PVE 战斗属性**；三项皆 0 时接口给 null。
  * equip.speed = 玩家跑图移动速度加成（一般只有脚部），不是精灵面板速度。
  * 真正 PVE 相关的数值在 bonus.attribute(六维) + bonus.desc（"背包内精灵体力+15点"这类）。
  * bonus.effective_pets: schema 说 null=对所有精灵生效；实测大量为 [] 空数组，语义按"无限制"处理。

用法：
    python ingest_gear.py                     # 全量（含 title/nature 修正），默认 5 线程
    python ingest_gear.py --workers 4         # 限速/并发
    python ingest_gear.py --limit 20          # 抽样快速验证
    python ingest_gear.py --dry-run           # 只统计不写盘
    python ingest_gear.py --no-title-nature   # 只做套装/装备（title/nature 保持旧样）
    python ingest_gear.py --no-cache          # 忽略磁盘缓存
断点续跑：详情响应逐条落盘 ontology/.cache/gear/{res}/{id}.json，文件存在即跳过网络。
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, XSD

BASE = "https://api.seerapi.com/v1/"
SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "seer-gear-abox.ttl")
CACHE = os.path.join(HERE, ".cache", "gear")
PETS_FROM = [os.path.join(HERE, f) for f in
             ("seer-pve-abox.ttl", "seer-pve-supp.ttl", "seer-game-abox.ttl")]
UA = {"User-Agent": "seer-gear/0.2"}

# 部位枚举的中文名（依据 SeerAPI name + 实例名抽样：head=战盔/帽、eye=护镜/面罩、
# waist=腰带/束腰、hand=护手/战刀/光剑、foot=战靴/底盘、bg=背景、mount=坐骑）
PART_CN = {"head": "头部", "eye": "眼部", "waist": "腰部", "hand": "手部",
           "foot": "足部", "bg": "背景", "mount": "坐骑"}

g = Graph()
g.bind("seer", SEER)
_stats = {}
# 空壳 bonus 判定用：黄蜂套装 1300083..86 这类 desc=""+六维全 0 的 bonus 不建个体
_SIX = ["atk", "def", "sp_atk", "sp_def", "spd", "hp"]
_SIX_PROP = {"atk": "bonusAtk", "def": "bonusDef", "sp_atk": "bonusSpAtk",
             "sp_def": "bonusSpDef", "spd": "bonusSpd", "hp": "bonusHp"}


def bump(k, n=1):
    _stats[k] = _stats.get(k, 0) + n


# ---------------------------------------------------------------------------
# 取数层：详情 + 磁盘缓存 + 重试
# ---------------------------------------------------------------------------
def _cache_path(res, rid):
    return os.path.join(CACHE, res, f"{rid}.json")


def _read_cache(res, rid):
    p = _cache_path(res, rid)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _write_cache(res, rid, obj):
    d = os.path.join(CACHE, res)
    os.makedirs(d, exist_ok=True)
    with open(_cache_path(res, rid), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True)


def fetch(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.2 * (i + 1))


def detail(res, rid, use_cache=True):
    if use_cache:
        c = _read_cache(res, rid)
        if c is not None:
            bump("cacheHit")
            return c
    d = fetch(f"{BASE}{res}/{rid}")
    if d is not None:
        _write_cache(res, rid, d)
        bump("netFetch")
    else:
        bump("FAIL", 1)
    return d


def list_ids(res):
    """list 端点只回 {id,url} —— 只用来取 id，name 必须走 detail。"""
    ids, url = [], f"{BASE}{res}?limit=100"
    while url:
        d = fetch(url)
        if not d:
            break
        ids += [x["id"] for x in d.get("results") or []]
        nxt = d.get("next")
        url = nxt if isinstance(nxt, str) else None
    return ids


def fetch_many(res, ids, workers, use_cache):
    out = {}
    if workers <= 1:
        for i in ids:
            out[i] = detail(res, i, use_cache)
        return out

    def one(i):
        time.sleep(0.05)  # 每线程轻微节流，避免把服务端打崩
        return i, detail(res, i, use_cache)

    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, i) for i in ids]
        for f in as_completed(futs):
            i, d = f.result()
            out[i] = d
            done += 1
            if done % 300 == 0:
                print(f"    {res}: {done}/{len(ids)}  {time.time()-t0:.0f}s "
                      f"(net={_stats.get('netFetch',0)} cache={_stats.get('cacheHit',0)} "
                      f"fail={_stats.get('FAIL',0)})", flush=True)
    return out


# ---------------------------------------------------------------------------
# 写图工具
# ---------------------------------------------------------------------------
def raw(v):
    return Literal(json.dumps(v, ensure_ascii=False, sort_keys=True)) if v is not None else None


def dec(v):
    return Literal(float(v), datatype=XSD.decimal)


def integer(v):
    return Literal(int(v), datatype=XSD.integer)


def emit_bonus_attrs(b, bonus_iri):
    """把 bonus.attribute(六维+percent+total) 与 bonus.other_attribute 结构化。"""
    a = (b or {}).get("attribute") or {}
    for k in _SIX:
        v = a.get(k)
        if v is not None:
            g.add((bonus_iri, SEER[_SIX_PROP[k]], dec(v)))
    if a.get("percent") is not None:
        g.add((bonus_iri, SEER.bonusPercent, Literal(bool(a["percent"]), datatype=XSD.boolean)))
    if a.get("total") is not None:
        g.add((bonus_iri, SEER.bonusTotal, dec(a["total"])))
    o = (b or {}).get("other_attribute") or {}
    for k, prop in (("hit_rate", "otherHitRate"), ("dodge_rate", "otherDodgeRate"),
                    ("crit_rate", "otherCritRate")):
        if o.get(k):
            g.add((bonus_iri, SEER[prop], integer(o[k])))


def bonus_is_meaningful(b):
    """空壳 bonus（desc=""、六维全 0、无 other/eid）不建个体。"""
    if not b:
        return False
    if (b.get("desc") or "").strip():
        return True
    if b.get("eid_effect"):
        return True
    a = b.get("attribute") or {}
    if any((a.get(k) or 0) for k in _SIX):
        return True
    o = b.get("other_attribute") or {}
    if any((o.get(k) or 0) for k in ("hit_rate", "dodge_rate", "crit_rate")):
        return True
    return False


def emit_eid(ee, owner_iri, url_ok=True):
    """bonus.eid_effect -> EidEffect 个体 + owner --bonusEffect--> eid；参数落在 owner 上。"""
    if not ee:
        return None
    eff = ee.get("effect") or {}
    eid = eff.get("id")
    if eid is None:
        return None
    e = SEER[f"eid_{eid}"]
    g.add((e, RDF.type, SEER.EidEffect))
    g.add((e, SEER.seerapiId, Literal(str(eid))))
    if eff.get("url"):
        g.add((e, SEER.sourceUrl, Literal(str(eff["url"]))))
    g.add((owner_iri, SEER.bonusEffect, e))
    if ee.get("effect_args") is not None:
        g.add((owner_iri, SEER.eidArgs, raw(ee["effect_args"])))
    return e


# ---------------------------------------------------------------------------
# 各资源
# ---------------------------------------------------------------------------
def emit_parts(type_map):
    for tid, t in type_map.items():
        name = str(t.get("name") or "").lower()
        cn = PART_CN.get(name, name)
        s = SEER[f"equippart_{tid}"]
        g.add((s, RDF.type, SEER.EquipPart))
        g.add((s, SEER.seerapiId, Literal(str(tid))))
        g.add((s, RDFS.label, Literal(cn, lang="zh")))
        g.add((s, RDFS.comment, Literal(f"SeerAPI equip_type.name={name}", lang="zh")))
        g.add((s, SEER.sourceUrl, Literal(f"{BASE}equip_type/{tid}")))
        bump("EquipPart")


def emit_occasions(occ_map):
    for oid, o in occ_map.items():
        s = SEER[f"occ_{oid}"]
        desc = str(o.get("description") or f"occasion_{oid}")
        g.add((s, RDF.type, SEER.EquipOccasion))
        g.add((s, SEER.seerapiId, Literal(str(oid))))
        g.add((s, RDFS.label, Literal(desc, lang="zh")))
        g.add((s, SEER.sourceUrl, Literal(f"{BASE}equip_effective_occasion/{oid}")))
        bump("EquipOccasion")


def emit_suit(su, pet_ids):
    sid = su.get("id")
    name = su.get("name")
    if not name:  # 硬失败：绝不再写 None
        raise RuntimeError(f"suit {sid} 无 name（接口异常）")
    s = SEER[f"suit_{sid}"]
    g.add((s, RDF.type, SEER.Suit))
    g.add((s, SEER.seerapiId, Literal(str(sid))))
    g.add((s, RDFS.label, Literal(str(name), lang="zh")))
    g.add((s, SEER.sourceUrl, Literal(f"{BASE}suit/{sid}")))
    if su.get("transform") is not None:
        g.add((s, SEER.transformSuit, Literal(bool(su["transform"]), datatype=XSD.boolean)))
    if su.get("tran_speed") is not None:
        g.add((s, SEER.tranSpeed, dec(su["tran_speed"])))

    eq_ids = [e["id"] for e in (su.get("equips") or []) if e.get("id") is not None]
    for eid in eq_ids:
        g.add((s, SEER.suitEquips, SEER[f"equip_{eid}"]))

    b = su.get("bonus")
    cm = [str(su.get("suit_desc"))] if su.get("suit_desc") else []
    if b and (b.get("desc") or "").strip():
        cm.append("套装效果:" + str(b["desc"]).strip())
    if cm:
        g.add((s, RDFS.comment, Literal(" | ".join(cm), lang="zh")))

    if b:
        bs = SEER[f"suitbonus_{sid}"]
        g.add((bs, RDF.type, SEER.SuitBonus))
        g.add((bs, SEER.seerapiId, Literal(str(b.get("id", sid)))))
        g.add((bs, SEER.sourceUrl, Literal(f"{BASE}suit/{sid}")))
        g.add((s, SEER.suitBonus, bs))
        if b.get("desc"):
            g.add((bs, SEER.bonusDesc, Literal(str(b["desc"]).strip(), lang="zh")))
        emit_bonus_attrs(b, bs)
        emit_eid(b.get("eid_effect"), bs)
        eps = b.get("effective_pets") or []
        if eps:
            g.add((bs, SEER.effectivePetId,
                   Literal(json.dumps([p.get("id") for p in eps], ensure_ascii=False))))
            for p in eps:
                pid = p.get("id")
                if pid is not None and str(pid) in pet_ids:
                    g.add((bs, SEER.effectiveForPet, SEER[f"pet_{pid}"]))
                else:
                    bump("Bonus.dangling_effective_pet")
        bump("SuitBonus")
    bump("Suit")


def emit_equip(eq):
    eid = eq.get("id")
    name = eq.get("name")
    if not name:
        raise RuntimeError(f"equip {eid} 无 name（接口异常）")
    s = SEER[f"equip_{eid}"]
    # 双写：既 PlayerEquip 又 Equip（seer-all.owl 查询期不做推理，朴素 ?x a seer:Equip 也要命中）
    g.add((s, RDF.type, SEER.PlayerEquip))
    g.add((s, RDF.type, SEER.Equip))
    g.add((s, SEER.seerapiId, Literal(str(eid))))
    g.add((s, RDFS.label, Literal(str(name), lang="zh")))
    g.add((s, SEER.sourceUrl, Literal(f"{BASE}equip/{eid}")))

    pt = (eq.get("part_type") or {}).get("id")
    if pt is not None:
        g.add((s, SEER.hasPart, SEER[f"equippart_{pt}"]))
        g.add((s, SEER.partType, integer(pt)))       # 原始枚举值，保 provenance
    else:
        raise RuntimeError(f"equip {eid} 无 part_type")

    if eq.get("speed") is not None:
        g.add((s, SEER.equipSpeed, dec(eq["speed"])))
    if eq.get("item"):
        g.add((s, SEER.itemRef, Literal(str(eq["item"].get("id")))))
    if eq.get("suit"):
        g.add((s, SEER.belongsToSuit, SEER[f"suit_{eq['suit']['id']}"]))
    if eq.get("occasion"):
        g.add((s, SEER.hasOccasion, SEER[f"occ_{eq['occasion']['id']}"]))

    pk = eq.get("pk_attribute")
    if pk:
        g.add((s, SEER.pkAttribute, raw(pk)))        # JSON 字面量（provenance）
        if pk.get("pk_hp") is not None:
            g.add((s, SEER.pkHp, integer(pk["pk_hp"])))
        if pk.get("pk_atk") is not None:
            g.add((s, SEER.pkAtk, integer(pk["pk_atk"])))
        if pk.get("pk_fire_range") is not None:
            g.add((s, SEER.pkFireRange, integer(pk["pk_fire_range"])))

    b = eq.get("bonus")
    if bonus_is_meaningful(b):
        es = SEER[f"equipbonus_{eid}"]
        g.add((es, RDF.type, SEER.EquipBonus))
        g.add((es, SEER.seerapiId, Literal(str(eid))))
        g.add((es, SEER.sourceUrl, Literal(f"{BASE}equip/{eid}")))
        g.add((s, SEER.equipBonus, es))
        if b.get("desc"):
            g.add((es, SEER.bonusDesc, Literal(str(b["desc"]).strip(), lang="zh")))
        emit_bonus_attrs(b, es)
        emit_eid(b.get("eid_effect"), es)
        bump("EquipBonus")
    elif b:
        bump("equip.empty_bonus")
    bump("Equip")


def emit_title(t):
    tid = t.get("id")
    name = t.get("name")
    if not name:
        raise RuntimeError(f"title {tid} 无 name（接口异常）")
    s = SEER[f"title_{tid}"]
    g.add((s, RDF.type, SEER.Title))
    g.add((s, SEER.seerapiId, Literal(str(tid))))
    g.add((s, RDFS.label, Literal(str(name), lang="zh")))
    g.add((s, SEER.sourceUrl, Literal(f"{BASE}title/{tid}")))
    if t.get("attr_bonus"):
        g.add((s, SEER.attrBonus, raw(t["attr_bonus"])))
    if t.get("desc"):
        g.add((s, RDFS.comment, Literal(str(t["desc"]), lang="zh")))
    bump("Title")


def emit_nature(n):
    nid = n.get("id")
    name = n.get("name")
    if not name:
        raise RuntimeError(f"nature {nid} 无 name（接口异常）")
    s = SEER[f"nature_{nid}"]
    g.add((s, RDF.type, SEER.Nature))
    g.add((s, SEER.seerapiId, Literal(str(nid))))
    g.add((s, RDFS.label, Literal(str(name), lang="zh")))
    g.add((s, SEER.sourceUrl, Literal(f"{BASE}nature/{nid}")))
    if n.get("attributes"):
        g.add((s, SEER.attributes, raw(n["attributes"])))
    cm = " | ".join(str(x) for x in [n.get("des"), n.get("des2")] if x)
    if cm:
        g.add((s, RDFS.comment, Literal(cm, lang="zh")))
    bump("Nature")


def emit_fires():
    fires = [
        ("fire_lvh", "绿火", "自动放的全局火：续命/命中/基础增益"),
        ("fire_jh", "金火", "借用增伤火焰（帖子里叫「借金火」）"),
        ("fire_xxx", "星星领火", "领的增伤火（thread-3409 提到可免领）"),
    ]
    for fid, nm, cm in fires:
        s = SEER[fid]
        g.add((s, RDF.type, SEER.Fire))
        g.add((s, RDFS.label, Literal(nm, lang="zh")))
        g.add((s, RDFS.comment, Literal(cm, lang="zh")))
        bump("Fire")


def load_pet_ids():
    """effective_pets 里只有真实存在于 Pet ABox 的精灵才建对象属性（不造桩个体，
    因为 test_regression.test_every_pet_has_label_and_type 要求每个 Pet 都有 label+seerapiId）。
    Pet 个体分散在 seer-pve-abox(62) + seer-pve-supp(698) + seer-game-abox(9)，故取并集。"""
    ids = set()
    for p in PETS_FROM:
        if not os.path.exists(p):
            continue
        pg = Graph()
        try:
            pg.parse(p, format="turtle")
        except Exception:
            continue
        ids |= {str(s).rsplit("#", 1)[-1][4:] for s in pg.subjects(RDF.type, SEER.Pet)}
    return ids


def main():
    args = sys.argv[1:]
    workers = 5
    if "--workers" in args:
        workers = int(args[args.index("--workers") + 1])
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    use_cache = "--no-cache" not in args
    do_tn = "--no-title-nature" not in args
    dry = "--dry-run" in args

    pet_ids = load_pet_ids()
    print(f"ingest_gear: workers={workers} cache={use_cache} title/nature={do_tn} "
          f"dry={dry} PetABox={len(pet_ids)}", flush=True)

    t_start = time.time()
    # 1) 部位 / 场合枚举（先建，部件要引用）
    type_map, occ_map = {}, {}
    for tid in list_ids("equip_type"):
        d = detail("equip_type", tid, use_cache)
        if d:
            type_map[tid] = {"id": d.get("id"), "name": d.get("name")}
    for oid in list_ids("equip_effective_occasion"):
        d = detail("equip_effective_occasion", oid, use_cache)
        if d:
            occ_map[oid] = {"id": d.get("id"), "description": d.get("description")}
    print(f"  部位={len(type_map)} 场合={len(occ_map)}", flush=True)
    emit_parts(type_map)
    emit_occasions(occ_map)

    # 2) 套装
    suit_ids = list_ids("suit")
    if limit:
        suit_ids = suit_ids[:limit]
    print(f"  suit ids={len(suit_ids)}", flush=True)
    suits = fetch_many("suit", suit_ids, workers, use_cache)
    for sid in sorted(suits):
        if suits[sid]:
            emit_suit(suits[sid], pet_ids)

    # 3) 部件
    eq_ids = list_ids("equip")
    if limit:
        eq_ids = eq_ids[:limit]
    print(f"  equip ids={len(eq_ids)}", flush=True)
    equips = fetch_many("equip", eq_ids, workers, use_cache)
    for eid in sorted(equips):
        if equips[eid]:
            emit_equip(equips[eid])

    # 4) 称号 / 性格（v0.1 同病：list 无 name → 全 None）
    if do_tn:
        t_ids = list_ids("title")
        if limit:
            t_ids = t_ids[:limit]
        print(f"  title ids={len(t_ids)}", flush=True)
        titles = fetch_many("title", t_ids, workers, use_cache)
        for tid in sorted(titles):
            if titles[tid]:
                emit_title(titles[tid])
        n_ids = list_ids("nature")
        if limit:
            n_ids = n_ids[:limit]
        print(f"  nature ids={len(n_ids)}", flush=True)
        natures = fetch_many("nature", n_ids, workers, use_cache)
        for nid in sorted(natures):
            if natures[nid]:
                emit_nature(natures[nid])
    else:
        # 不重跑 title/nature 时，保持旧 ABox 里已有个体：从旧产物原样搬过来
        print("  [skip] title/nature（--no-title-nature）", flush=True)
        if os.path.exists(OUT):
            old = Graph()
            old.parse(OUT, format="turtle")
            for cls, keep in ((SEER.Title, ["attrBonus"]), (SEER.Nature, ["attributes"])):
                for s in old.subjects(RDF.type, cls):
                    for p, o in old.predicate_objects(s):
                        g.add((s, p, o))
                    bump(cls.split("#")[-1])

    # 5) 火（SeerAPI 无资源，手工）
    emit_fires()

    # ---- 自检（写盘前）----
    n_suit = len(set(g.subjects(RDF.type, SEER.Suit)))
    n_eq = len(set(g.subjects(RDF.type, SEER.PlayerEquip)))
    n_part = len(set(g.subjects(RDF.type, SEER.EquipPart)))
    n_sb = len(set(g.subjects(RDF.type, SEER.SuitBonus)))
    n_eb = len(set(g.subjects(RDF.type, SEER.EquipBonus)))
    bad = [str(s) for s in g.subjects(RDF.type, SEER.Suit)
           if not any(str(o) != "None" for o in g.objects(s, RDFS.label))]
    if bad:
        raise RuntimeError(f"{len(bad)} 个 Suit 的 label 仍为 None，拒绝写盘")
    no_part = [s for s in g.subjects(RDF.type, SEER.PlayerEquip) if g.value(s, SEER.hasPart) is None]
    if no_part:
        raise RuntimeError(f"{len(no_part)} 个 PlayerEquip 缺 hasPart，拒绝写盘")

    print(f"\n  自检通过：Suit={n_suit} PlayerEquip={n_eq} EquipPart={n_part} "
          f"SuitBonus={n_sb} EquipBonus={n_eb}", flush=True)
    print(f"  参考耗时 {time.time()-t_start:.0f}s  "
          f"net={_stats.get('netFetch',0)} cache={_stats.get('cacheHit',0)} "
          f"fail={_stats.get('FAIL',0)}", flush=True)

    if dry:
        print("\n  --dry-run：不写盘", flush=True)
    else:
        g.serialize(OUT, format="turtle")
        print("\n完成 ->", OUT, flush=True)
    print("三元组 =", len(g))
    for k in sorted(_stats):
        print(f"  {k}: {_stats[k]}")


if __name__ == "__main__":
    main()