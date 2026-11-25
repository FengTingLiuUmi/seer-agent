# -*- coding: utf-8 -*-
"""适配上下文组装：目标 Boss + 参考思路/阵容(召回) + 玩家可替换候选(带属性/定位/数量)。

注意：本脚本只负责拼「三条证据链」，不 responsables改阵容——改阵容是模型的活。
召回侧不改、不动玩家缓存，二者在适配前保持解耦。

运行：PYTHONPATH=.pylibs;kb;ontology;player PYTHONUTF8=1 python player/adapt_context.py 瓦坎 地狱 4
"""
import os
import sys
import json

from rdflib import Graph, Namespace, RDF, RDFS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "kb"))
sys.path.insert(0, os.path.join(ROOT, "ontology"))

import player_cache as PC  # noqa: E402
import plan as P  # noqa: E402

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
ROLE_CN = {"attacker": "强攻", "support": "辅助", "tank": "站场",
           "reflect": "弹伤", "firstStrike": "必先"}
MIMI = "753949294"


def pet_meta():
    """seerapiId -> {name, type(元素列表), roles(定位本地名列表)}。"""
    g = Graph()
    g.parse(os.path.join(ROOT, "ontology", "seer-all.owl"), format="xml")
    out = {}
    for pet in g.subjects(RDF.type, SEER.Pet):
        pid = str(g.value(pet, SEER.seerapiId) or "")
        if not pid:
            continue
        els, roles = set(), set()
        for tc in g.objects(pet, SEER.hasTypeCombination):
            for e in g.objects(tc, SEER.combinationOf):
                lb = g.value(e, RDFS.label)
                if lb:
                    n = str(lb).replace("系", "").strip()
                    if n:
                        els.add(n)
        for r in g.objects(pet, PVE.hasRole):
            roles.add(str(r).rsplit("#", 1)[-1])
        name = next((str(x) for x in g.objects(pet, RDFS.label)), "")
        out[pid] = {"name": name, "type": sorted(els), "roles": sorted(roles)}
    return out


def main():
    factor, difficulty, stage = sys.argv[1], sys.argv[2], int(sys.argv[3])

    # ① 目标 Boss
    doc = P.load_doc(factor, difficulty)
    st = next(s for s in doc["stages"] if s["stage"] == stage)
    counter = P._counter_profiles().get(f"{factor}#{difficulty}#{stage}", {})
    boss = {
        "factor": factor, "difficulty": difficulty, "stage": stage,
        "boss_pet_id": st.get("boss_pet_id"),
        "traits": st.get("traits"), "mech": st.get("mech"),
        "boss_type": counter.get("boss_type"), "counter(克制它的属性)": counter.get("counter"),
        "why": st.get("why"),
    }

    # ② 参考思路/阵容（本关自身 + 相似 boss topk，持有无关）
    r = P.plan(factor, difficulty, stage, k=8)
    refs, seen = [], set()
    for sg in st.get("strategies", []):
        k2 = ("本关", sg.get("plan"))
        if k2 in seen or not sg.get("pets"):
            continue
        seen.add(k2)
        refs.append({"来源": "本关策略", "思路": sg.get("plan"), "阵容": sg.get("pets"), "why": sg.get("why")})
    for c in r.get("similar", []):
        for sg in (c.get("stage_card", {}).get("strategies") or []):
            if not sg.get("pets"):
                continue
            k2 = (c["doc_id"], sg.get("plan"))
            if k2 in seen:
                continue
            seen.add(k2)
            refs.append({"来源": f"{c['factor']}#{c['difficulty']}#{c['stage']}",
                         "思路": sg.get("plan"), "阵容": sg.get("pets"), "why": sg.get("why")})
    refs = refs[:15]

    # ③ 玩家可替换候选（有定位的打手，带属性/定位/数量）
    meta = pet_meta()
    conn = PC.connect()
    cands = []
    for sp in PC.species_owned(conn, MIMI):
        m = meta.get(sp)
        if not m or not m["roles"]:
            continue
        cands.append({"species_id": sp, "name": m["name"], "type": m["type"],
                      "定位": [ROLE_CN.get(x, x) for x in m["roles"]],
                      "只数": PC.count_species(conn, MIMI, sp)})
    conn.close()

    print(json.dumps({"boss": boss, "参考思路与阵容": refs, "玩家可替换候选": cands},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()