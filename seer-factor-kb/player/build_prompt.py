# -*- coding: utf-8 -*-
"""把「召回结果 + 玩家持有」固化成可复跑的 prompt，供 LLM 产出逐关「改后阵容」。

输入：因子 + 难度 [+ 单关号]；输出：一段自包含中文 prompt（持有池 + 逐关目标/硬门/克制/参考阵容）。
可复跑：python player/build_prompt.py 瓦坎 地狱   （产出全文并落盘 player/prompt_<因子>_<难度>.txt）

持有池 = 有定位的持有精灵 ∪ （本关/相似关参考阵容里出现且玩家持有的精灵，即使无定位）——保证"直接照抄"可行。

运行：PYTHONPATH=.pylibs;kb;ontology;player PYTHONUTF8=1 python player/build_prompt.py 瓦坎 地狱
"""
import os
import sys

from rdflib import Graph, Namespace, RDF, RDFS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "kb"))
sys.path.insert(0, os.path.join(ROOT, "ontology"))

import player_cache as PC  # noqa: E402
import plan as P  # noqa: E402
import mechanisms as M  # noqa: E402

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
ROLE_CN = {"attacker": "强攻", "support": "辅助", "tank": "站场",
           "reflect": "弹伤", "firstStrike": "必先"}
MIMI = "753949294"


def pet_meta():
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


def owned_candidates(extra_names):
    """持有池 = 有定位的持有 ∪ (extra_names 里玩家持有的，即使无定位)。

    extra_names 用缓存 clean 名解析（species_id_by_name 精确匹配），避开本体 label 的后缀问题。
    """
    meta = pet_meta()
    conn = PC.connect()
    rows, seen_sid = [], set()
    for sp in PC.species_owned(conn, MIMI):
        m = meta.get(sp)
        if not m or not m["roles"]:
            continue
        rows.append({"name": m["name"], "type": m["type"],
                     "roles": [ROLE_CN.get(x, x) for x in m["roles"]],
                     "n": PC.count_species(conn, MIMI, sp)})
        seen_sid.add(sp)
    for nm in extra_names:
        sp = PC.species_id_by_name(conn, MIMI, nm)
        if not sp or sp in seen_sid:
            continue
        m = meta.get(sp)
        if not m:
            continue
        rows.append({"name": nm, "type": m["type"],
                     "roles": [ROLE_CN.get(x, x) for x in m["roles"]] or ["—"],
                     "n": PC.count_species(conn, MIMI, sp)})
        seen_sid.add(sp)
    conn.close()
    dedup = {}
    for r in rows:
        dedup.setdefault(r["name"], r)
    return list(dedup.values())


def stage_context(factor, difficulty, stage):
    doc = P.load_doc(factor, difficulty)
    st = next(s for s in doc["stages"] if s["stage"] == stage)
    ctr = P._counter_profiles().get(f"{factor}#{difficulty}#{stage}", {})
    hard = [M.SLUG2CI[x] for x in st.get("mech", []) if x in P.HARD]

    r = P.plan(factor, difficulty, stage, k=6)
    refs, seen, names = [], set(), set()
    for sg in st.get("strategies", []):
        if not sg.get("pets"):
            continue
        k2 = ("本关", sg.get("plan"))
        if k2 in seen:
            continue
        seen.add(k2)
        refs.append(f"  ·本关　思路={sg['plan']}｜阵容={sg['pets']}｜{sg.get('why') or ''}")
        names.update(sg["pets"])
    for c in r.get("similar", []):
        for sg in (c.get("stage_card", {}).get("strategies") or []):
            if not sg.get("pets"):
                continue
            k2 = (c["doc_id"], sg.get("plan"))
            if k2 in seen:
                continue
            seen.add(k2)
            refs.append(f"  ·相似[{c['factor']}#{c['difficulty']}#{c['stage']}] "
                        f"思路={sg['plan']}｜阵容={sg['pets']}｜{(sg.get('why') or '')[:60]}")
            names.update(sg["pets"])
    return {
        "stage": stage,
        "boss_type": ctr.get("boss_type"),
        "counter": ctr.get("counter"),
        "hard": hard,
        "traits": st.get("traits"),
        "refs": refs[:8],
        "names": names,
    }


def render_prompt(factor, difficulty, stage_ctxs, candidates):
    L = []
    L.append("你是赛尔号 PVE 打手。基于【玩家可替换精灵池】和【逐关目标+参考思路】，为每关输出改后可行阵容。")
    L.append("")
    L.append("【约束】")
    L.append("1. lineup 只能用精灵池里的精灵，同一物种最多上×N只（N=其后的只数）。")
    L.append("2. 必须满足硬门：只吃暴击→要必暴来源(帝皇之御守御八方/引爆手)；单精灵→只能1只；免疫物攻→走特攻强攻或弹伤；免疫特攻→走物攻；裸伤上限→卡裸伤；")
    L.append("3. 沿用参考思路；参考阵容里有池子里没有的精灵，就按「克制属性 ∩ 定位」在池里换。")
    L.append("4. 某关无解则 lineup 为空数组，reason 写明缺什么。")
    L.append("")
    L.append("【玩家可替换精灵池】")
    for c in sorted(candidates, key=lambda x: -x["n"]):
        L.append(f"- {c['name']}｜type={c['type']}｜定位={c['roles']}｜×{c['n']}")
    L.append("")
    L.append(f"【目标因子】{factor} · {difficulty}")
    for sc in stage_ctxs:
        L.append("")
        L.append(f"[第{sc['stage']}关] Boss属性={sc['boss_type'] or '?'}｜克制它的属性={sc['counter'] or []}｜"
                 f"硬门={sc['hard'] or '无'}｜威胁={sc['traits']}")
        for rf in sc["refs"]:
            L.append(rf)
    L.append("")
    L.append("【输出】只输出一个 JSON 数组，不要任何解释：")
    L.append('[{"stage":1,"lineup":["精灵名(职责)"],"reason":"一句话说明硬门/克制/定位如何满足、替换了谁"}]')
    return "\n".join(L)


def main():
    factor, difficulty = sys.argv[1], sys.argv[2]
    stage_arg = sys.argv[3] if len(sys.argv) > 3 else None

    doc = P.load_doc(factor, difficulty)
    stages = [s["stage"] for s in doc["stages"]]
    if stage_arg:
        stages = [int(stage_arg)]

    ctxs = [stage_context(factor, difficulty, st) for st in stages]
    ref_names = set()
    for sc in ctxs:
        ref_names |= sc["names"]
    cands = owned_candidates(ref_names)
    prompt = render_prompt(factor, difficulty, ctxs, cands)
    print(prompt)

    suffix = f"_{stage_arg}" if stage_arg else ""
    out = os.path.join(HERE, f"prompt_{factor}_{difficulty}{suffix}.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n--- 已落盘：{out}", file=sys.stderr)


if __name__ == "__main__":
    main()