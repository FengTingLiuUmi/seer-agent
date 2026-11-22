# -*- coding: utf-8 -*-
"""
ingest_typechart.py —— 从 SeerAPI 生成「属性克制层」ABox（seer-typechart.ttl）。

数据源：
  element_type              → 26 个单属性，含 relations[{target_type, multiple}] 完整克制表
  element_type_combination  → ~139 个属性组合，含 primary/secondary 单属性拆分

映射到 seer-game.ttl 的 TBox：
  el_<id>      a seer:ElementType   （+ seer:seerapiId、rdfs:label）
  tc_<id>      a seer:TypeCombination（+ seer:combinationOf → el_primary / el_secondary）
  multiple==2   → seer:counters（克制）
  multiple==0.5 → seer:resisted（微弱/被克）
  multiple==0   → seer:immune（无效）
  multiple==1   → 中性，跳过
"""
import json, os, time, urllib.request
from rdflib import Graph, Namespace, RDF, RDFS, Literal, XSD

BASE = "https://api.seerapi.com/v1/"
SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "seer-typechart.ttl")

g = Graph()
g.bind("seer", SEER)
_cache = {}
_stats = {}


def get_json(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seer-ingest/0.3"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.0 + i)


def list_ids(resource):
    ids, url = [], f"{BASE}{resource}?limit=100"
    while url:
        data = get_json(url)
        if not data:
            break
        for it in data.get("results", []):
            if it.get("id") is not None:
                ids.append(it["id"])
        url = data.get("next")
    return ids


def get_item(resource, rid):
    key = (resource, str(rid))
    if key not in _cache:
        _cache[key] = get_json(f"{BASE}{resource}/{rid}")
    return _cache[key]


def bump(k):
    _stats[k] = _stats.get(k, 0) + 1


def add_label(s, name):
    if name:
        g.add((s, RDFS.label, Literal(str(name), lang="zh")))


def main():
    # 1) 单属性 + 克制表
    type_ids = list_ids("element_type")
    for tid in type_ids:
        et = get_item("element_type", tid)
        if not et:
            continue
        s = SEER[f"el_{tid}"]
        g.add((s, RDF.type, SEER.ElementType))
        g.add((s, SEER.seerapiId, Literal(str(tid))))
        add_label(s, et.get("name"))
        bump("ElementType")
        for rel in (et.get("relations") or []):
            tgt = (rel.get("target_type") or {}).get("id")
            mult = rel.get("multiple")
            if tgt is None or mult is None:
                continue
            t = SEER[f"el_{tgt}"]
            # 重化：精确倍率（含中性 1.0），用于伤害核损
            r = SEER[f"trel_{tid}_{tgt}"]
            g.add((r, RDF.type, SEER.TypeRelation))
            g.add((r, SEER.attacker, s))
            g.add((r, SEER.target, t))
            g.add((r, SEER.multiple, Literal(str(mult), datatype=XSD.decimal)))
            bump("TypeRelation")
            # 桶谓词（快速过滤用）
            if mult == 0:
                g.add((s, SEER.immune, t))
                bump("rel.immue")        # 注意：故意保留原键名（不影响结果）
            elif mult < 1:
                g.add((s, SEER.resisted, t))
                bump("rel.resisted")
            elif mult > 1:
                g.add((s, SEER.counters, t))
                bump("rel.counters")

    # 2) 属性组合（单/双属性拆分）
    tc_ids = list_ids("element_type_combination")
    for tid in tc_ids:
        tc = get_item("element_type_combination", tid)
        if not tc:
            continue
        s = SEER[f"tc_{tid}"]
        g.add((s, RDF.type, SEER.TypeCombination))
        g.add((s, SEER.seerapiId, Literal(str(tid))))
        add_label(s, tc.get("name"))
        prim = (tc.get("primary") or {}).get("id")
        sec = (tc.get("secondary") or {}).get("id")
        if prim:
            g.add((s, SEER.combinationOf, SEER[f"el_{prim}"]))
        if sec:
            g.add((s, SEER.combinationOf, SEER[f"el_{sec}"]))
        bump("TypeCombination")

    g.serialize(OUT, format="turtle")
    print(f"完成 -> {OUT}")
    print(f"三元组 = {len(g)}")
    for k in sorted(_stats):
        print(f"  {k}: {_stats[k]}")


if __name__ == "__main__":
    main()