# -*- coding: utf-8 -*-
"""根据 pets-supplement.json 生成本体补丁 seer-pve-supp.ttl：
- 新精灵(id 不在本体) → 建 Pet 个体(seerapiId/label/type/变体别名/备注)。
- 已是本体的精灵 → 只补 skos:altLabel 变体别名。
运行：PYTHONPATH=.pylibs PYTHONUTF8=1 python build_supp.py
"""
import os, re, json
from rdflib import Graph, RDF, RDFS, Namespace, SKOS, Literal

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
# 多批补充表（按顺序合并，同 seerapiId 去重；别名累加）
SUPP_FILES = [
    f"{HERE}/../scrape/pets-supplement.json",
    f"{HERE}/../scrape/pets-supplement2.json",
    f"{HERE}/../scrape/pets-boss-supp.json",
]


def ln(u): return str(u).rsplit("#", 1)[-1]
def label(node, g):
    for o in g.objects(node, RDFS.label):
        return str(o)
    return ln(node)
def id_of(node, g):
    v = g.value(node, SEER.seerapiId)
    return str(v) if v is not None else None


def norm_elem(s):
    return s.replace("系", "").replace(" ", "").strip()


g = Graph()
g.parse(f"{HERE}/seer-all.owl", format="xml")

# 元素集合 -> TypeCombination 资源
tc_by = {}
for tc in g.subjects(RDF.type, SEER.TypeCombination):
    elems = frozenset(norm_elem(label(e, g)) for e in g.objects(tc, SEER.combinationOf))
    tc_by[elems] = tc

id2iri = {}
for p in g.subjects(RDF.type, SEER.Pet):
    pid = id_of(p, g)
    if pid:
        id2iri[pid] = p
existing_ids = set(id2iri)

data_pets = []
for fp in SUPP_FILES:
    if not os.path.exists(fp):
        continue
    with open(fp, encoding="utf-8") as f:
        data_pets += json.load(f).get("pets") or []

g2 = Graph()
g2.bind("seer", SEER)
g2.bind("pve", PVE)
g2.bind("skos", SKOS)
g2.bind("rdfs", RDFS)

new_count = alt_count = 0
miss_type = []
seen_pid = set()
for p in data_pets:
    pid = str(p.get("seerapiId", "")).strip()
    name = (p.get("name") or "").strip()
    if not pid or not name:
        continue
    if pid in seen_pid:  # 跨批重复：只再补别名
        pet = id2iri.get(pid)
        if pet is not None:
            for v in [str(x).strip() for x in (p.get("variants") or []) if str(x).strip()]:
                if v != name:
                    g2.add((pet, SKOS.altLabel, Literal(v, lang="zh")))
                    alt_count += 1
        continue
    seen_pid.add(pid)
    variants = [str(v).strip() for v in (p.get("variants") or []) if str(v).strip()]
    note = (p.get("note") or "").strip()
    if not pid or not name:
        continue
    raw_types = p.get("type") or []
    if isinstance(raw_types, str):
        raw_types = [raw_types]
    types = [norm_elem(t) for t in raw_types if norm_elem(t)]
    comment = note
    if variants:
        comment = (comment + " | 别名: " + "/".join(variants)).strip(" |")

    # 注意：本脚本是可重入的——每次都要为补充表里的每只精灵写全 type/label/seerapiId/属性组合，
    # 否则第二次运行时这些「已存在」的个体只会剩 altLabel，label 丢失（曾踩过）。
    pet = id2iri.get(pid) or SEER[f"pet_{pid}"]
    g2.add((pet, RDF.type, SEER.Pet))
    g2.add((pet, SEER.seerapiId, Literal(pid)))
    # 无条件写 label：seer-all.owl 既是输入又含本脚本上次的产物，
    # 用「g 里已有 label」做判断会让产物在第二次运行时丢失（曾踩两次）。
    g2.add((pet, RDFS.label, Literal(name, lang="zh")))
    for v in variants:
        if v != name:
            g2.add((pet, SKOS.altLabel, Literal(v, lang="zh")))
            alt_count += 1
    if comment:
        g2.add((pet, RDFS.comment, Literal(comment, lang="zh")))
    elems = frozenset(types)
    tc = tc_by.get(elems)
    if tc is not None:
        g2.add((pet, SEER.hasTypeCombination, tc))
    elif elems:
        miss_type.append((name, pid, list(types)))
    # 种族值（Boss 面板/伤害计算器底座）
    bs = p.get("base_stats")
    if isinstance(bs, dict):
        for k, pred in (("hp", SEER.baseHp), ("atk", SEER.baseAtk), ("def", SEER.baseDef),
                        ("sp_atk", SEER.baseSpAtk), ("sp_def", SEER.baseSpDef), ("spd", SEER.baseSpd)):
            if bs.get(k) is not None:
                g2.add((pet, pred, Literal(int(bs[k]))))
    if pid not in existing_ids:
        new_count += 1

out = f"{HERE}/seer-pve-supp.ttl"
g2.serialize(out, format="turtle")
# 供交付文档/报告引用的统计（避免手抄数字过期）
with open(f"{HERE}/supp-stats.json", "w", encoding="utf-8") as f:
    json.dump({"new_individuals": new_count, "alt_labels": alt_count,
               "supp_pets": len(seen_pid), "onto_pets": len(existing_ids) + new_count},
              f, ensure_ascii=False, indent=1)
print(f"新增宠物个体 = {new_count}，补别名三元组 = {alt_count}")
if miss_type:
    print("未能映射属性组合的：", miss_type)
print("写出", out)