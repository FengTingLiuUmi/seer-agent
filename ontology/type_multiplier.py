# -*- coding: utf-8 -*-
"""type_multiplier.py —— 赛尔号克制倍率换算（按玩家定案规则，精确到 0.5/0.25/…）。
规则来源（用户定案）：
  一. 单 vs 单：矩阵值 ∈ {2,1,0.5,0}；0=攻击方对守方打不出红伤，但技能效果仍触发。
  二/三. 恰好一侧为双属性时，拆成两个“单vs单”配对值 v1,v2：
         - v1==2 且 v2==2  -> 4
         - v1==0 或 v2==0   -> (v1+v2)/4
         - 其余            -> (v1+v2)/2
  双 vs 双：r1 = combine(攻对守属性1), r2 = combine(攻对守属性2)；最终 = (r1+r2)/2
"""
import json, os
from rdflib import Graph, Namespace, RDF, RDFS

SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
TTC = os.path.join(HERE, "seer-typechart.ttl")


def load():
    g = Graph()
    g.parse(TTC, format="turtle")
    single = {}          # (a_ele_id, d_ele_id) -> float
    eid2name = {}
    name2eid = {}
    for e in g.subjects(RDF.type, SEER.ElementType):
        sid = int(str(g.value(e, SEER.seerapiId)))
        nm = str(g.value(e, RDFS.label)) if g.value(e, RDFS.label) else ""
        eid2name[sid] = nm
        if nm:
            name2eid.setdefault(nm, sid)
    for r in g.subjects(RDF.type, SEER.TypeRelation):
        a = int(str(g.value(g.value(r, SEER.attacker), SEER.seerapiId)))
        d = int(str(g.value(g.value(r, SEER.target), SEER.seerapiId)))
        m = float(g.value(r, SEER.multiple))
        single[(a, d)] = m
    # 属性组合 -> 构成单属性 id 列表（无序）
    tc2elems = {}
    for tc in g.subjects(RDF.type, SEER.TypeCombination):
        tid = int(str(g.value(tc, SEER.seerapiId)))
        elems = sorted(int(str(g.value(e, SEER.seerapiId)))
                       for e in g.objects(tc, SEER.combinationOf))
        tc2elems[tid] = elems
    return single, name2eid, eid2name, tc2elems


SINGLE, NAME2EID, EID2NAME, TC2ELEMS = load()


def _resolve(name):
    if name in NAME2EID:
        return NAME2EID[name]
    g = NAME2EID.get(name.rstrip("系"))
    return g


def combine2(v1, v2):
    if v1 == 2 and v2 == 2:
        return 4.0
    if v1 == 0 or v2 == 0:
        return (v1 + v2) / 4.0
    return (v1 + v2) / 2.0


def multiplier(a_elems, d_elems):
    """a_elems/d_elems: 1~2 个单属性 id 列表（无序）。"""
    a, d = list(a_elems), list(d_elems)
    if len(a) == 1 and len(d) == 1:
        return SINGLE[(a[0], d[0])]
    if len(a) == 1 and len(d) == 2:
        return combine2(SINGLE[(a[0], d[0])], SINGLE[(a[0], d[1])])
    if len(a) == 2 and len(d) == 1:
        return combine2(SINGLE[(a[0], d[0])], SINGLE[(a[1], d[0])])
    if len(a) == 2 and len(d) == 2:
        r1 = combine2(SINGLE[(a[0], d[0])], SINGLE[(a[1], d[0])])
        r2 = combine2(SINGLE[(a[0], d[1])], SINGLE[(a[1], d[1])])
        return (r1 + r2) / 2.0
    raise ValueError("bad elems")


def elements_of(tc_id):
    """属性组合 tc_id 的构成单属性 id 列表（1~2 个，无序）。"""
    return list(TC2ELEMS.get(int(tc_id), []))


def share_element(tc_a, tc_b):
    """两属性组合是否含共同单属性（仅作其它用途，不是本系判定）。"""
    return bool(set(elements_of(tc_a)) & set(elements_of(tc_b)))


def is_same_type(tc_a, tc_b):
    """本系判定：属性组合作为集合完全一致。
    注意：双属性精灵一般要「双属性技能」且组合一致才吃本系；双属性精灵用单属性技能不吃本系。
    """
    pa = set(elements_of(tc_a))
    sa = set(elements_of(tc_b))
    return bool(pa) and pa == sa


STAB = 1.5  # 本系加成倍率（用户确认 ×1.5）；判定用 is_same_type


def stab_multiplier(pet_tc, skill_tc):
    return STAB if is_same_type(pet_tc, skill_tc) else 1.0


def by_names(a_names, d_names):
    a = [_resolve(n) for n in a_names]
    d = [_resolve(n) for n in d_names]
    if any(x is None for x in a + d):
        return None
    return multiplier(a, d)


def main():
    out = {
        "name_map": {i: EID2NAME.get(i) for i in sorted(EID2NAME)},
        "tests": [],
    }
    cases = [
        ("单vs单 圣灵->草 = 2", ["圣灵"], ["草"], 2.0),
        ("单vs单 王->自然 = 0.5", ["王"], ["自然"], 0.5),
        ("单vs单 邪灵->神灵 = 0", ["邪灵"], ["神灵"], 0.0),
        ("双vs单 圣灵自然 -> 草 = 4", ["圣灵", "自然"], ["草"], 4.0),
        ("双vs单 邪灵神秘 -> 神灵 = 0.5", ["邪灵", "神秘"], ["神灵"], 0.5),
        ("单vs双 王 -> 自然战斗 = 1.25", ["王"], ["自然", "战斗"], 1.25),
        ("双vs双 自然战斗 -> 光飞行 = 1.5", ["自然", "战斗"], ["光", "飞行"], 1.5),
        ("双vs双 远古战斗 -> 龙暗影 = 2.375", ["远古", "战斗"], ["龙", "暗影"], 2.375),
    ]
    for label, a, d, exp in cases:
        got = by_names(a, d)
        ok = (got is not None) and abs(got - exp) < 1e-9
        out["tests"].append({"label": label, "a": a, "d": d, "expected": exp, "got": got, "pass": ok})

    p = os.path.join(HERE, "type_multiplier_out.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote", p, "| pass=", sum(1 for t in out["tests"] if t["pass"]), "/", len(out["tests"]))


if __name__ == "__main__":
    main()