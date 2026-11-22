# -*- coding: utf-8 -*-
"""把 SSOT docs（kb/docs/**/*.json）ingest 成本体 ABox：seer-factors-abox.ttl。
- 仅追加「本体里还没有的因子」（按 label 判重），不碰 seer-boss-abox.ttl 的 33 个老因子，避免重复个体。
- 产出 Factor / FactorStage / Enemy / FactorDifficulty + hasStage/hasEnemy/hasMechanic/isApex/
  bossHp/bossTrait/bossTypeCombination/forFactor/difficulty/stageNumber/bannedPet/counteredBy。
- counteredBy / bannedPet 只引用能消歧到 seer:Pet 的；消不出来的省略（宁缺毋滥）。
- 运行后需 sync.merge_check()（会把本文件并进 seer-all.owl）。
"""
import os, re, sys, json, hashlib, glob

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
ONT = os.path.join(HERE, "..", "ontology").replace("\\", "/")
KB = os.path.join(HERE, "..", "kb").replace("\\", "/")
sys.path.insert(0, ONT.replace("\\", "/"))
sys.path.insert(0, KB.replace("\\", "/"))

from rdflib import Graph, RDF, RDFS, Namespace, SKOS, Literal
import type_multiplier as tm

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

DIFF = {"地狱": "hard", "困难": "normal", "简单": "easy"}
DIFF_IRI = {"hard": PVE.diff_hard, "normal": PVE.diff_normal, "easy": PVE.diff_easy}

G = Graph()
# 基础图 = 除 seer-factors-abox.ttl 外的全部本体文件（factors-abox 是本脚本自身可重建产物，不能作为判重依据，否则重跑会跳过已入库因子并覆盖丢数据）。
for _f in ["seer-game.ttl", "seer-pve.ttl", "seer-pve-alias.ttl", "seer-pve-roles.ttl",
           "seer-game-abox.ttl", "seer-typechart.ttl", "seer-pve-abox.ttl", "seer-pve-supp.ttl",
           "seer-gear-abox.ttl", "seer-boss-abox.ttl"]:
    _p = f"{ONT}/{_f}"
    if os.path.exists(_p):
        try:
            G.parse(_p, format="turtle")
        except Exception as _e:  # noqa: BLE001
            print(f"  skip parse {_f}: {_e}")

# --- 本体已有因子（按 label 定位；按 因子×难度 判重）---
existing_factor_labels = {str(o) for s in G.subjects(RDF.type, SEER.Factor) for o in G.objects(s, RDFS.label)}
existing_slugs = {str(s).rsplit("#", 1)[-1].replace("factor_", "") for s in G.subjects(RDF.type, SEER.Factor)}
fact_iri_by_label = {str(G.value(s, RDFS.label)): s for s in G.subjects(RDF.type, SEER.Factor)}
_DIFF_IRI_REV = {str(v): k for k, v in DIFF_IRI.items()} if False else {str(PVE.diff_hard): "hard", str(PVE.diff_normal): "normal", str(PVE.diff_easy): "easy"}
existing_fd = {}  # factor label -> set(diff_local)
for st in G.subjects(RDF.type, SEER.FactorStage):
    d = G.value(st, PVE.difficulty)
    dl = _DIFF_IRI_REV.get(str(d)) if d is not None else None
    if not dl:
        continue
    for f in G.subjects(SEER.hasStage, st):
        existing_fd.setdefault(str(G.value(f, RDFS.label)), set()).add(dl)

# --- 属性组合：元素集合 → IRI ---
NAMES = sorted({v for v in tm.EID2NAME.values()}, key=len, reverse=True)
tc_by_elems = {}
for tc in G.subjects(RDF.type, SEER.TypeCombination):
    elems = frozenset(str(G.value(e, RDFS.label)) for e in G.objects(tc, SEER.combinationOf))
    tc_by_elems[elems] = tc


def segment(s):
    out, i = [], 0
    while i < len(s):
        for n in NAMES:
            if s.startswith(n, i):
                out.append(n)
                i += len(n)
                break
        else:
            return None
    return out


# --- 精灵消歧：名字/别名 → pet IRI ---
def core(s):
    return re.sub(r"[（(].*?[)）]", "", s).replace("·", "").replace(" ", "").strip()


pet_exact, pet_contains = {}, []
for p in G.subjects(RDF.type, SEER.Pet):
    lab = str(G.value(p, RDFS.label) or "")
    pid = str(G.value(p, SEER.seerapiId) or "")
    for t in {lab, core(lab), pid}:
        if t:
            pet_exact.setdefault(t, p)
    pet_contains.append((p, core(lab)))


def resolve_pet(tok):
    t = core(tok)
    if not t:
        return None
    if t in pet_exact:
        return pet_exact[t]
    for p, cn in pet_contains:
        if cn and (t in cn or cn in t):
            return p
    return None


def slug_for(factor):
    n = re.sub(r"[\s·]", "", factor)
    if n in existing_slugs:
        return n
    # 优先用精灵 id；否则用 factor 名的短 md5（稳定，不与老 slug 冲突）
    p = resolve_pet(factor)
    if p is not None:
        pid = str(G.value(p, SEER.seerapiId) or "")
        if pid:
            cand = f"p{pid}"
            if cand not in existing_slugs:
                return cand
    return "f" + hashlib.md5(factor.encode("utf-8")).hexdigest()[:10]


def mech_iri(slug):
    return PVE["mech_" + slug]


out = Graph()
out.bind("seer", SEER)
out.bind("pve", PVE)
out.bind("rdfs", RDFS)

with open(f"{KB}/docs/catalog.json", encoding="utf-8") as f:
    cat = json.load(f)
n_factor = n_stage = n_ban = n_counter = 0
factor_slug_cache = {}

for c in cat:
    with open(os.path.join(KB, c["path"]), encoding="utf-8") as f:
        doc = json.load(f)
    factor, difficulty = doc["factor"], doc["difficulty"]
    diff = DIFF.get(difficulty)
    if not diff:
        continue
    if diff in existing_fd.get(factor, set()):
        continue  # 该 因子×难度 已在（老 boss-abox），不重复
    fac_iri = fact_iri_by_label.get(factor)
    if fac_iri is None:
        slug = factor_slug_cache.setdefault(factor, slug_for(factor))
        fac_iri = SEER[f"factor_{slug}"]
        out.add((fac_iri, RDF.type, SEER.Factor))
        out.add((fac_iri, RDFS.label, Literal(factor, lang="zh")))
        n_factor += 1
    else:
        # 复用老因子个体，只补缺失难度（slug 继承老 IRI，保证 stage_<slug>_<diff>_<n> 一致）
        slug = str(fac_iri).rsplit("#", 1)[-1].replace("factor_", "")
    # FactorDifficulty
    fd = PVE[f"fd_{slug}_{diff}"]
    out.add((fd, RDF.type, PVE.FactorDifficulty))
    out.add((fd, RDFS.label, Literal(f"{factor}·{difficulty}", lang="zh")))
    out.add((fd, PVE.difficulty, DIFF_IRI[diff]))
    out.add((fd, PVE.forFactor, fac_iri))
    for b in doc.get("ban") or []:
        p = resolve_pet(str(b))
        if p is not None:
            out.add((fd, PVE.bannedPet, p))
            n_ban += 1
    # stages
    for st in doc.get("stages", []):
        n = int(st["stage"])
        st_iri = SEER[f"stage_{slug}_{diff}_{n}"]
        en_iri = PVE[f"enemy_{slug}_{diff}_{n}"]
        out.add((fac_iri, SEER.hasStage, st_iri))
        out.add((st_iri, RDF.type, SEER.FactorStage))
        out.add((st_iri, RDFS.label, Literal(f"{factor}·{difficulty} 第{n}关", lang="zh")))
        out.add((st_iri, PVE.difficulty, DIFF_IRI[diff]))
        out.add((st_iri, PVE.stageNumber, Literal(n, datatype=XSD.integer)))
        out.add((st_iri, PVE.hasEnemy, en_iri))
        out.add((st_iri, PVE.isApex, Literal(bool(st.get("apex")), datatype=XSD.boolean)))
        # enemy
        out.add((en_iri, RDF.type, PVE.Enemy))
        out.add((en_iri, RDFS.label, Literal(f"{factor}-第{n}关 Boss", lang="zh")))
        if st.get("boss_hp") is not None:
            out.add((en_iri, PVE.bossHp, Literal(int(st["boss_hp"]), datatype=XSD.integer)))
        if st.get("traits"):
            out.add((en_iri, PVE.bossTrait, Literal(str(st["traits"]), lang="zh")))
        for m in st.get("mech") or []:
            out.add((en_iri, PVE.hasMechanic, mech_iri(m)))
        # Boss 本体建模：物种 + 数值缩放 + 单精灵关 + 属性回填
        bpid = st.get("boss_pet_id")
        bpet = resolve_pet(str(bpid)) if bpid is not None else None
        if bpet is not None:
            out.add((en_iri, PVE.bossSpecies, bpet))
        bt = (st.get("boss_type") or "").replace("·", "").replace(" ", "")
        seg = segment(bt) if bt else None
        tc = tc_by_elems.get(frozenset(seg)) if seg else None
        if tc is None and bpet is not None:
            tc = G.value(bpet, SEER.hasTypeCombination)  # 缺 boss_type 时从物种类型兜底回填
        if tc is not None:
            out.add((en_iri, PVE.bossTypeCombination, tc))
        if st.get("boss_is_single_pet") is not None:
            out.add((en_iri, PVE.bossIsSinglePet, Literal(bool(st["boss_is_single_pet"]), datatype=XSD.boolean)))
        if st.get("boss_atk_scale") is not None:
            out.add((en_iri, PVE.bossAtkScale, Literal(float(st["boss_atk_scale"]), datatype=XSD.decimal)))
        if st.get("boss_def_scale") is not None:
            out.add((en_iri, PVE.bossDefScale, Literal(float(st["boss_def_scale"]), datatype=XSD.decimal)))
        src = ""
        _strats = st.get("strategies") or []
        if _strats:
            if isinstance(_strats[0], dict):
                src = " / ".join(str(x.get("text", "")) for x in _strats)[:40]
            else:
                src = str(_strats)[:40]
        if src:
            out.add((en_iri, RDFS.comment, Literal(f"来源 factors-final；攻略示例 {src}", lang="zh")))
        for pet in st.get("pets") or []:
            p = resolve_pet(str(pet))
            if p is not None:
                out.add((en_iri, PVE.counteredBy, p))
                n_counter += 1
        n_stage += 1

outpath = f"{ONT}/seer-factors-abox.ttl"
out.serialize(outpath, format="turtle")
print(f"新因子 = {n_factor}，新关卡(阶段) = {n_stage}，bannedPet = {n_ban}，counteredBy = {n_counter}")
print("写出", outpath)