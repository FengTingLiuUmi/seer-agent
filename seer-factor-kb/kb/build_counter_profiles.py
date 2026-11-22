# -*- coding: utf-8 -*-
"""派生每关「克制面」：克制该关 Boss 的技能属性集合（倍率 >= 2）。

数据源：
  - 本体 seer-all.owl：pet → hasTypeCombination → combinationOf → 元素名（覆盖最全）
  - scrape/pets-boss-supp.json：兜底
  - ontology/type_multiplier.py：克制换算

产出：kb/counter_profiles.json（key=因子#难度#关），供 plan.R4 用。幂等派生。
运行：PYTHONUTF8=1 PYTHONPATH=.pylibs;kb;ontology python kb/build_counter_profiles.py
"""
import os
import sys
import json
import glob

from rdflib import Graph, Namespace, RDF, RDFS

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SCRAPE = os.path.join(HERE, "..", "scrape").replace("\\", "/")
ONT = os.path.join(HERE, "..", "ontology").replace("\\", "/")
sys.path.insert(0, ONT)
sys.path.insert(0, HERE)

import type_multiplier as TM  # noqa: E402

DOCS = f"{HERE}/docs"
OUT = f"{HERE}/counter_profiles.json"
SEER = Namespace("http://example.org/seer#")


def strip_xi(s):
    return str(s).replace("系", "").strip()


def pet2type_from_onto():
    g = Graph()
    g.parse(os.path.join(ONT, "seer-all.owl"), format="xml")
    out = {}
    for pet in g.subjects(RDF.type, SEER.Pet):
        pid = str(g.value(pet, SEER.seerapiId) or "")
        if not pid:
            continue
        els = set()
        for tc in g.objects(pet, SEER.hasTypeCombination):
            for e in g.objects(tc, SEER.combinationOf):
                lbl = g.value(e, RDFS.label)
                if lbl:
                    n = strip_xi(lbl)
                    if n:
                        els.add(n)
        if els:
            out[pid] = sorted(els)
    return out


def main():
    pid2type = pet2type_from_onto()
    with open(os.path.join(SCRAPE, "pets-boss-supp.json"), encoding="utf-8") as f:
        supp = json.load(f)
    for p in supp.get("pets", []):
        ts = [strip_xi(t) for t in (p.get("type") or []) if str(t).strip()]
        ts = [t for t in ts if t]
        pid2type.setdefault(str(p["seerapiId"]), ts)

    all_elems = sorted(TM.NAME2EID.keys())

    def counter_of(boss_types):
        out = []
        ok = False
        for sn in all_elems:
            m = TM.by_names([sn], boss_types)
            if m is None:
                continue
            ok = True
            if m > 1.0:
                out.append(sn)
        return out if ok else None

    profiles = {}
    mech_map = {}
    miss = []
    for fp in sorted(glob.glob(f"{DOCS}/*/*.json")):
        if fp.endswith("catalog.json"):
            continue
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        fac, dif = d["factor"], d["difficulty"]
        for s in d.get("stages", []):
            sid = f"{fac}#{dif}#{s['stage']}"
            mech_map[sid] = {
                "doc_id": f"{fac}#{dif}",
                "factor": fac,
                "difficulty": dif,
                "stage": s["stage"],
                "mech": s.get("mech") or [],
            }
            els = pid2type.get(str(s.get("boss_pet_id") or ""))
            co = counter_of(els) if els else None
            if not co:
                miss.append(sid)
                continue
            profiles[sid] = {
                "doc_id": f"{fac}#{dif}",
                "factor": fac,
                "difficulty": dif,
                "stage": s["stage"],
                "boss_type": "/".join(els),
                "counter": co,
            }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=0)
    with open(f"{HERE}/mech_map.json", "w", encoding="utf-8") as f:
        json.dump(mech_map, f, ensure_ascii=False, indent=0)
    print(f"克制面 = {len(profiles)} 关；mech_map = {len(mech_map)} 关；缺 = {len(miss)}")
    if miss:
        print("缺失样例:", miss[:12])


if __name__ == "__main__":
    main()