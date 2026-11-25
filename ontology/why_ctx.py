# -*- coding: utf-8 -*-
"""why_ctx.py —— 给 strategies[].why 清洗提供可核对事实。

用法（workdir=workspace 根）：
    python seer-factor-kb/ontology/why_ctx.py <因子名> [难度]
输出：每关 Boss 属性/血量/traits，每个 strategy 的参战精灵（属性组合、对 Boss 的
攻击倍率、本系、前几个攻击技能含威力/先制/必中/PP/效果全文）。
只读，不改任何文件。
"""
import io
import json
import os
import sys

from rdflib import Graph, Namespace, RDF, RDFS, URIRef

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import type_multiplier as TM  # noqa: E402

SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
G = None
BYLABEL = {}
TCNAME = {}


def graph():
    global G
    if G is None:
        G = Graph()
        G.parse(os.path.join(HERE, "seer-all.owl"), format="xml")
    return G


def build_index():
    g = graph()
    for p in g.subjects(RDF.type, SEER.Pet):
        for lb in g.objects(p, RDFS.label):
            BYLABEL[str(lb).strip()] = p
    for tc, tid in [(tc, g.value(tc, SEER.seerapiId)) for tc in g.subjects(RDF.type, SEER.TypeCombination)]:
        if tid is None:
            continue
        elems = TM.elements_of(int(str(tid)))
        TCNAME[int(str(tid))] = "".join(TM.EID2NAME.get(e, "?") for e in elems)


def pet_tc(pet):
    tid = graph().value(pet, SEER.hasTypeCombination)
    if tid is None:
        return None, ""
    i = int(str(tid).split("_")[-1])
    return i, TCNAME.get(i, "")


def _txt(node, pred):
    v = graph().value(node, pred)
    return "" if v is None else str(v)


def skills_of(pet, limit=6):
    g = graph()
    rows = []
    for s in g.objects(pet, SEER.hasSkill):
        pw = g.value(s, SEER.power)
        pr = g.value(s, SEER.priority)
        rows.append((float(pw) if pw is not None else -1.0,
                     float(pr) if pr is not None else 0.0, s))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    out = []
    for pw, pr, s in rows[:limit]:
        cat = _txt(s, SEER.skillCategory)
        eff = [_txt(e, SEER.effectInfo) for e in g.objects(s, SEER.hasSkillEffect)]
        eff = [e for e in eff if e and e.strip()]
        mh = g.value(s, SEER.mustHit)
        pp = g.value(s, SEER.maxPP)
        name = _txt(s, RDFS.label) or str(s).split("#")[-1]
        out.append({
            "name": name,
            "power": int(pw) if pw >= 0 else None,
            "pri": int(pr),
            "cat": cat,
            "mustHit": (str(mh) == "true" or str(mh) == "1") if mh is not None else None,
            "pp": int(pp) if pp is not None else None,
            "eff": eff[:3],
        })
    return out


def strat_pets(name):
    p = BYLABEL.get(name)
    if p is None:
        return None
    tc, tcn = pet_tc(p)
    return {"pet": p, "tc": tc, "type": tcn}


def main():
    factor = sys.argv[1] if len(sys.argv) > 1 else None
    diff = sys.argv[2] if len(sys.argv) > 2 else "地狱"
    if not factor:
        print("usage: why_ctx.py <因子名> [难度]")
        return 2
    root = os.path.abspath(os.path.join(HERE, ".."))
    docp = os.path.join(root, "kb", "docs", factor, diff + ".json")
    doc = json.load(open(docp, encoding="utf-8"))
    build_index()
    print(f"# DOC {doc['doc_id']}  {docp}")
    for st in doc["stages"]:
        bt = st.get("boss_type") or "?"
        print("=" * 78)
        print(f"## stage {st['stage']}  boss_type={bt}  boss_hp={st.get('boss_hp')}  "
              f"single={st.get('boss_is_single_pet')}  apex={st.get('apex')}")
        print("   traits:", st.get("traits"))
        print("   mech:", ", ".join(st.get("mech") or []))
        if st.get("why"):
            print("   stage.why(保留):", st["why"])
        b_elems = [TM.NAME2EID.get(n) for n in _split(bt)]
        for j, sp in enumerate(st.get("strategies") or []):
            print(f"--- [{j}] {sp.get('plan')}   src={sp.get('source')}")
            print(f"    now_why={sp.get('why')!r}")
            for pn in sp.get("pets") or []:
                info = strat_pets(pn)
                if info is None:
                    print(f"    * {pn}  <<< 本体查不到这个精灵名（可能简称/未入库）")
                    continue
                tcn = info["type"]
                mult = None
                if tcn and b_elems and all(x is not None for x in b_elems):
                    try:
                        mult = TM.multiplier(TM.elements_of(info["tc"]), b_elems)
                    except Exception:
                        mult = None
                print(f"    * {pn}  属性={tcn}  (自身属性打boss={mult})")
                for sk in skills_of(info["pet"], 5):
                    eff = " / ".join(sk["eff"])
                    print(f"        · {sk['name']} 威力{sk['power']} 先制{sk['pri']:+d} "
                          f"{sk['cat']} 必中={sk['mustHit']} PP={sk['pp']}"
                          + (f"  效果:{eff}" if eff else ""))
    return 0


def _split(bt):
    bt = (bt or "").replace("·", "").replace("/", "").replace("系", "")
    names = sorted(TM.NAME2EID.keys(), key=len, reverse=True)
    out, i = [], 0
    while i < len(bt):
        for n in names:
            if bt.startswith(n, i):
                out.append(n)
                i += len(n)
                break
        else:
            i += 1
    return out


if __name__ == "__main__":
    sys.exit(main())