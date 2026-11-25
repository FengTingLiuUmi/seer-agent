# -*- coding: utf-8 -*-
"""ingest_effects.py v1.0 —— 效果/道具层 ABox：把 SeerAPI 里“战斗效果”这一整族资源灌进本体。

背景：seer-onto.ttl 早早声明了 Buff / BuffType / BattleEffect / FieldEffect / Item / Gem /
Mintmark / PetEffect / PetClass / PetAdvance / EnergyBead / SoulmarkTag 这些类，
但一直是 0 个体（空壳分支）；soulmark 只有 72 个（PVE 精灵池那点）。
本脚本把 SeerAPI 对应资源全量取下来，生成 seer-effects-abox.ttl。

数据源（schema: https://api.seerapi.com/v1/schemas/<res>/$id）
  buff 3555 / buff_type 2      战斗 buff（含“吸血”“减伤”等 tag + desc）
  battle_effect 43 / *_type 5  战斗效果（伤害类，带 resistance）
  field_effect 3 / *_type 2    场地效果
  soulmark 2167 / soulmark_tag 20   魂印（desc / pve_effective / pet / tag）
  pet_effect 300 / group 50    精灵特性（含 star_level）
  energy_bead 48               能量珠（use_times + 绑定道具）
  gem 245 / gem_category 36    宝石（等级 / 代 / 镶嵌率 / 对应道具）
  pet_advance 28               精灵进阶（技能 + 魂印 + 六维）
  mintmark_class/type/rarity   刻印分类枚举
  [--with-big] mintmark 3843 / item 12802 / item_category 21

约定（与既有 ABox 一致）：
  * 个体 IRI = seer:{资源名}_{id}，如 seer:buff_1 / seer:soulmark_135 / seer:pet_2419
  * 名字一律 rdfs:label（@zh），并写 seer:seerapiId 便于回溯
  * 记录里的嵌套 {id,url} 引用 -> 对象属性（属性名 = 字段名 camelCase），
    目标 IRI 用 url 里的资源名派生，因此跨资源天然接得上
  * 已存在的属性（如 :pveEffective / :baseAttrValue / :useTimes）直接复用，不另造词

断点续跑：详情落盘 .cache/effects/{res}/{id}.json，文件在即跳过网络。
用法：
    python ingest_effects.py --sample 3        # 每类抽 3 条，先验证字段映射
    python ingest_effects.py --workers 8       # 常规全量（core 集）
    python ingest_effects.py --with-big        # 追加 mintmark / item（慢，建议后台）
    python ingest_effects.py --no-cache        # 忽略缓存
"""
import json, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, XSD

BASE = "https://api.seerapi.com/v1/"
SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "seer-effects-abox.ttl")
CACHE = os.path.join(HERE, ".cache", "effects")
UA = {"User-Agent": "seer-effects/1.0"}

# 资源 -> (类名, 中文标签, 字段白名单 or None=全字段)
CORE_RES = [
    ("buff_type", "BuffType", "战斗Buff分类", ["buff"]),
    ("buff", "Buff", "战斗Buff（增益/减益/吸血/减伤等）", None),
    ("battle_effect_type", "BattleEffectType", "战斗效果分类", ["name", "effect"]),
    ("battle_effect", "BattleEffect", "战斗效果（伤害修正/抵抗）", None),
    ("field_effect_type", "FieldEffectType", "场地效果分类", ["effect"]),
    ("field_effect", "FieldEffect", "场地效果", None),
    ("soulmark_tag", "SoulmarkTag", "魂印标签", ["name", "soulmark"]),
    ("soulmark", "Soulmark", "魂印（PVE 核心）", None),
    ("pet_effect_group", "PetEffectGroup", "精灵特性分组", ["name", "effect"]),
    ("pet_effect", "PetEffect", "精灵特性", ["name", "desc", "effect", "effect_alias", "star_level", "effect_group"]),
    ("energy_bead", "EnergyBead", "能量珠", None),
    ("gem_category", "GemCategory", "宝石分类", None),
    ("gem", "Gem", "宝石", None),
    ("pet_advance", "PetAdvance", "精灵进阶", None),
    ("mintmark_type", "MintmarkType", "刻印类型", None),
    ("mintmark_rarity", "MintmarkRarity", "刻印稀有度", None),
    ("mintmark_class", "MintmarkClass", "刻印分类", ["id", "name", "mintmark"]),
]

BIG_RES = [
    ("item_category", "ItemCategory", "道具分类", ["id", "name", "max", "item"]),
    ("item", "Item", "道具（含战斗消耗品）", None),
    ("mintmark", "Mintmark", "刻印（能力/技能）", None),
]

# 与既有词表不一致的别名修正（SeerAPI 字段 -> 本体已用属性）
FIELD_ALIAS = {
    "pve_effective": "pveEffective",
    "use_times": "useTimes",
    "base_attr_value": "baseAttrValue",
    "max_attr_value": "maxAttrValue",
    "extra_attr_value": "extraAttrValue",
}

# 标量/字面量字段的改名：:effect 在 seer-status.ttl 里已属 StatusAilment 专用，
# 刻印/魂印复用会撞 domain，故按资源改名。
SCALAR_ALIAS = {
    ("mintmark", "effect"): "mintmarkEffect",
    ("soulmark", "effect"): "soulmarkEffect",
    ("pet_advance", "base_stats"): "advanceBaseStats",
    ("energy_bead", "ability_buff"): "beadAbilityBuff",
}

# 引用类字段（值含 id/url 或 id/url 列表）单独取名，避免与同名数值属性打架
#   (资源, 字段) -> 对象属性名；未列出的引用字段用 "<资源名>Ref" 规则（见 obj_prop_name）
REF_ALIAS = {
    ("buff", "type"): "buffType",
    ("soulmark", "tag"): "soulmarkTag",
    ("soulmark", "pet"): "affectsPet",
    ("soulmark", "intensified_to"): "intensifiedTo",
    ("soulmark", "from"): "derivedFrom",
    ("soulmark", "advance"): "advanceOf",
    ("battle_effect", "type"): "battleEffectType",
    ("field_effect", "type"): "fieldEffectType",
    ("battle_effect_type", "effect"): "containsEffect",
    ("field_effect_type", "effect"): "containsEffect",
    ("pet_effect", "effect"): "petEffectBody",
    ("pet_effect", "effect_group"): "effectGroup",
    ("pet_effect_group", "effect"): "containsEffect",
    ("energy_bead", "item"): "grantedItem",
    ("energy_bead", "effect"): "beadEffect",
    ("gem", "category"): "gemCategory",
    ("gem", "item"): "grantedItem",
    ("gem", "prev_level_gem"): "prevLevelGem",
    ("gem", "next_level_gem"): "nextLevelGem",
    ("gem", "effect"): "gemEffect",
    ("mintmark", "type"): "mintmarkType",
    ("mintmark", "rarity"): "mintmarkRarity",
    ("mintmark", "mintmark_class"): "mintmarkClass",
    ("mintmark", "pet"): "affectsPet",
    ("mintmark", "skill"): "grantsSkill",
    ("mintmark", "connect"): "connectTo",
    ("mintmark_class", "mintmark"): "containsMintmark",
    ("mintmark_type", "mintmark"): "containsMintmark",
    ("mintmark_rarity", "mintmark"): "containsMintmark",
    ("item", "category"): "itemCategory",
    ("item_category", "item"): "containsItem",
    ("pet_advance", "pet"): "advancesPet",
    ("pet_advance", "skill"): "grantsSkill",
    ("pet_advance", "soulmark"): "grantsSoulmark",
    ("buff_type", "buff"): "containsBuff",
    ("soulmark_tag", "soulmark"): "tagsSoulmark",
}

g = Graph()
g.bind("seer", SEER)
g.bind("owl", OWL)
g.bind("rdfs", RDFS)
_stats = {}


def bump(k, n=1):
    _stats[k] = _stats.get(k, 0) + n


def camel(s):
    if s in FIELD_ALIAS:
        return FIELD_ALIAS[s]
    parts = re.split(r"[_\-]", s)
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


# ---------------------------------------------------------------------------
# 取数
# ---------------------------------------------------------------------------
def _cp(res, rid):
    return os.path.join(CACHE, res, f"{rid}.json")


def fetch(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.0 * (i + 1))


def detail(res, rid, use_cache=True):
    if use_cache:
        p = _cp(res, rid)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    bump("cache")
                    return json.load(f)
            except Exception:
                pass
    d = fetch(f"{BASE}{res}/{rid}")
    if d is None:
        bump("FAIL")
        return None
    os.makedirs(os.path.join(CACHE, res), exist_ok=True)
    with open(_cp(res, rid), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, sort_keys=True)
    bump("net")
    return d


def list_ids(res):
    ids, url = [], f"{BASE}{res}?limit=100"
    while url:
        d = fetch(url)
        if not d:
            break
        ids += [x["id"] for x in (d.get("results") or [])]
        nxt = d.get("next")
        if isinstance(nxt, dict):
            url = f"{BASE}{res}?limit=100&offset={nxt.get('offset', 0)}"
        elif isinstance(nxt, str) and nxt:
            url = nxt
        else:
            url = None
    return ids


# ---------------------------------------------------------------------------
# 写图
# ---------------------------------------------------------------------------
def pname(p):
    return str(p).split("#")[-1].split("/")[-1]


def resource_of(url):
    """https://api.seerapi.com/v1/buff/12 -> ("buff", 12)"""
    m = re.match(r".*/v1/([a-z_]+)/(\d+)$", url or "")
    return (m.group(1), int(m.group(2))) if m else (None, None)


def lit(v, key):
    if isinstance(v, bool):
        return Literal(v, datatype=XSD.boolean)
    if isinstance(v, int):
        return Literal(v, datatype=XSD.integer)
    if isinstance(v, float):
        return Literal(v, datatype=XSD.decimal)
    s = str(v)
    # 中文文本打 @zh；纯数字/枚举串不打
    if re.search(r"[\u4e00-\u9fff]", s):
        return Literal(s, lang="zh")
    return Literal(s)


declared_props = set()


def emit(res, cls_cn, rec):
    rid = rec.get("id")
    if rid is None:
        return None
    cls, cn = cls_cn
    subj = SEER[f"{res}_{rid}"]
    g.add((subj, RDF.type, OWL.NamedIndividual))
    g.add((subj, RDF.type, SEER[cls]))
    g.add((subj, SEER.seerapiId, Literal(str(rid))))
    g.add((subj, SEER.sourceUrl, Literal(f"{BASE}{res}/{rid}")))
    name = rec.get("name") if isinstance(rec.get("name"), str) else None
    if not name:
        tag = rec.get("tag")
        name = tag if isinstance(tag, str) else None
    if name:
        g.add((subj, RDFS.label, Literal(str(name), lang="zh")))
    return subj


SKIP_FIELDS = {"id", "url", "hash"}


def emit_fields(subj, res, rec, whitelist):
    for k, v in rec.items():
        if k in SKIP_FIELDS:
            continue
        if whitelist is not None and k not in whitelist:
            continue
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, dict):
            r, i = resource_of(v.get("url"))
            if i is None:
                # 内嵌结构体（如刻印 effect={"arg":10,"effect":101}）按 JSON 字面量存
                prop = SEER[SCALAR_ALIAS.get((res, k)) or (f"{res}Effect" if k == "effect" else camel(k))]
                g.add((subj, prop, Literal(json.dumps(v, ensure_ascii=False, sort_keys=True))))
                declare(prop, "DatatypeProperty", pname(subj), None)
                continue
            prop = SEER[REF_ALIAS.get((res, k)) or camel(k)]
            g.add((subj, prop, SEER[f"{r or k}_{i}"]))
            declare(prop, "ObjectProperty", pname(subj), r or k)
        elif isinstance(v, list):
            if all(isinstance(x, dict) and resource_of(x.get("url"))[1] is not None for x in v):
                prop = SEER[REF_ALIAS.get((res, k)) or camel(k)]
                for x in v:
                    r, i = resource_of(x["url"])
                    g.add((subj, prop, SEER[f"{r}_{i}"]))
                declare(prop, "ObjectProperty", pname(subj), r)
            else:
                # 数值/枚举/字符串数组（如 icon:[7]、tag:[...]）存成 JSON 字面量
                prop = SEER[SCALAR_ALIAS.get((res, k)) or (f"{res}Effect" if k == "effect" else camel(k))]
                g.add((subj, prop, Literal(json.dumps(v, ensure_ascii=False, sort_keys=True))))
                declare(prop, "DatatypeProperty", pname(subj), None)
        else:
            # :effect 已被 seer-status.ttl 用作 StatusAilment 专属数据属性，本模块一律改用 <资源>Effect
            prop = SEER[SCALAR_ALIAS.get((res, k)) or (f"{res}Effect" if k == "effect" else camel(k))]
            g.add((subj, prop, lit(v, k)))
            declare(prop, "DatatypeProperty", pname(subj), None)


def declare(prop, kind, dom, rng):
    if pname(prop) in declared_props:
        return
    declared_props.add(pname(prop))
    g.add((prop, RDF.type, OWL[kind]))
    g.add((prop, RDFS.label, Literal(pname(prop))))
    if dom:
        g.add((prop, RDFS.domain, SEER[dom]))
    if rng and kind == "ObjectProperty":
        # 目标类名按资源名规范：buff -> Buff
        g.add((prop, RDFS.range, SEER[rng[:1].upper() + rng[1:]]))


def declare_class(cls, cn):
    c = SEER[cls]
    g.add((c, RDF.type, OWL.Class))
    g.add((c, RDFS.label, Literal(cn, lang="zh")))


# ---------------------------------------------------------------------------
# 精灵占位个体：魂印表覆盖全服 2579 只精灵，而本体只精模 PVE 精灵池（~764）。
# 不补占位就会留下 seer:pet_XXXX 悬空引用（查询拿不到名字）。占位只写
# rdfs:label + seerapiId，不写属性组合/六维，避免冒充精模数据。
# ---------------------------------------------------------------------------
PETS_FROM = [os.path.join(HERE, f) for f in
             ("seer-pve-abox.ttl", "seer-pve-supp.ttl", "seer-game-abox.ttl",
              "seer-factors-abox.ttl", "seer-boss-abox.ttl")]
PETS_INDEX = os.path.join(HERE, "..", "scrape", "pets-index.json")


def existing_pets():
    out = set()
    for p in PETS_FROM:
        if not os.path.exists(p):
            continue
        t = Graph()
        t.parse(p, format="turtle")
        out |= {int(ln_local(s)[4:]) for s in t.subjects(RDF.type, SEER.Pet)
                if ln_local(s).startswith("pet_") and ln_local(s)[4:].isdigit()}
    return out


def ln_local(u):
    return str(u).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def stub_pets():
    if not os.path.exists(PETS_INDEX):
        print("  !! 找不到 pets-index.json，跳过占位精灵", flush=True)
        return
    idx = {int(p["id"]): p for p in json.load(open(PETS_INDEX, encoding="utf-8"))}
    have = existing_pets()
    referenced = set()
    for o in (o for s, p, o in g.triples((None, None, None))
              if str(o).startswith(str(SEER) + "pet_")):
        tail = ln_local(o)
        if tail.startswith("pet_") and tail[4:].isdigit():
            referenced.add(int(tail[4:]))
    missing = sorted(referenced - have)
    n = 0
    for pid in missing:
        info = idx.get(pid)
        s = SEER[f"pet_{pid}"]
        g.add((s, RDF.type, OWL.NamedIndividual))
        g.add((s, RDF.type, SEER.Pet))
        g.add((s, SEER.seerapiId, Literal(str(pid))))
        nm = (info or {}).get("name")
        # pets-index 未收录的也补名字占位，否则占位个体缺 label 会触发 pet 完整性断言
        g.add((s, RDFS.label, Literal(nm or f"未收录·{pid}", lang="zh")))
        if nm:
            n += 1
    print(f"  占位精灵：引用 {len(referenced)}，已有精模 {len(referenced & have)}，"
          f"新建 {len(missing)}（其中 {n} 个带名字）", flush=True)


# ---------------------------------------------------------------------------
def ingest(res, cls, cn, whitelist, limit, workers, use_cache):
    t0 = time.time()
    ids = list_ids(res)
    if limit:
        ids = ids[:limit]
    if not ids:
        print(f"  !! {res}: 取不到 id 列表", flush=True)
        return
    print(f"  {res}: {len(ids)} 条", flush=True)
    declare_class(cls, cn)
    got = {}
    if workers <= 1:
        for i in ids:
            got[i] = detail(res, i, use_cache)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(detail, res, i, use_cache) for i in ids]
            done = 0
            for f in as_completed(futs):
                d = f.result()
                if d:
                    got[d["id"]] = d
                done += 1
                if done % 500 == 0:
                    print(f"    {res} {done}/{len(ids)} {time.time()-t0:.0f}s "
                          f"cache={_stats.get('cache',0)} net={_stats.get('net',0)} fail={_stats.get('FAIL',0)}",
                          flush=True)
    n = 0
    for rid, rec in got.items():
        s = emit(res, (cls, cn), rec)
        if s is None:
            continue
        emit_fields(s, res, rec, whitelist)
        n += 1
    print(f"  {res}: 写图 {n} 个个体，{time.time()-t0:.0f}s", flush=True)


def main():
    argv = sys.argv[1:]
    limit = None
    if "--sample" in argv:
        limit = int(argv[argv.index("--sample") + 1])
    workers = 8
    if "--workers" in argv:
        workers = int(argv[argv.index("--workers") + 1])
    use_cache = "--no-cache" not in argv
    jobs = list(CORE_RES)
    if "--with-big" in argv:
        jobs += BIG_RES
    if "--only" in argv:
        want = set(x.strip() for x in argv[argv.index("--only") + 1].replace("+", ",").split(",") if x.strip())
        jobs = [j for j in (CORE_RES + BIG_RES) if j[0] in want]
        if not jobs:
            print("  !! --only 没有任何命中资源")
            return

    # 增量：已有产物先装载，--only 局部补数时不会把其它资源清掉（--fresh 强制重建）
    if os.path.exists(OUT) and "--fresh" not in argv:
        g.parse(OUT, format="turtle")
        print(f"  增量模式：已装载 {os.path.basename(OUT)}，{len(g)} 三元组", flush=True)

    # --purge res1,res2：先清掉这些资源的个体再按新规则重建（改映射后修脏数据用）
    if "--purge" in argv:
        for rname in [x.strip() for x in argv[argv.index("--purge") + 1].split(",") if x.strip()]:
            pre = str(SEER) + rname + "_"
            # 只清本资源的个体（IRI 尾部是纯数字），否则 purge soulmark 会误杀 soulmark_tag_*
            victims = [s for s in set(g.subjects())
                       if str(s).startswith(pre) and str(s)[len(pre):].isdigit()]
            for s in victims:
                for t in list(g.triples((s, None, None))):
                    g.remove(t)
            print(f"  purge {rname}: 清掉 {len(victims)} 个个体", flush=True)

    for res, cls, cn, wl in jobs:
        ingest(res, cls, cn, wl, limit, workers, use_cache)

    if "--no-stub" not in argv:
        stub_pets()

    g.serialize(OUT, format="turtle")
    print(f"\n==> {OUT}")
    print(f"    三元组 {len(g)}  统计 {_stats}", flush=True)


if __name__ == "__main__":
    main()