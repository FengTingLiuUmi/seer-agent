# -*- coding: utf-8 -*-
"""plan 查询层：R1(因子×难度整块直查) + R2(机制相似) + R3(数值模板相似) + RRF + 硬门标注。
- 召回单元=单关；R1 返回 SSOT 文档整块。
- 候选都回读 docs/<doc_id> 取权威内容（不信索引快照）。
- 冷启动：R1 无攻略且 R2/R3 空时，用 stats.json 的 P(机制|第N关,难度) 先验给 hint。
"""
import os, re, json, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
DOCS = f"{HERE}/docs"
IDX = f"{HERE}/index"

from whoosh import index
from whoosh.qparser import QueryParser

import mechanisms as M

# 结构性硬门（用于“缺口”标注；反制要求更严）
HARD = {"singlePet", "immunePhysical", "immuneSpecial", "onlyCrit", "rawCap",
        "panelImmune", "onlyFirstStrike", "immunePower", "hitDebuff", "twoLife", "undying"}

_ix = None


def _open_index():
    global _ix
    if _ix is None:
        _ix = index.open_dir(IDX)
    return _ix


def load_doc(factor, difficulty):
    """R1：直读 SSOT 文档整块。"""
    fp = os.path.join(DOCS, factor, f"{difficulty}.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    return None


def load_catalog():
    with open(f"{DOCS}/catalog.json", encoding="utf-8") as f:
        return json.load(f)


def _mech_query(slugs, k=20):
    if not slugs:
        return []
    ix = _open_index()
    qp = QueryParser("mech", schema=ix.schema)
    q = qp.parse(" ".join(slugs))
    with ix.searcher() as s:
        hits = s.search(q, limit=k)
        return [(h["stage_id"], h["doc_id"], h["factor"], h["difficulty"], h["stage"], h.score) for h in hits]


def _template_query(boss_type, hp, fx, js, k=20):
    toks = []
    if boss_type:
        toks.append(boss_type.replace("·", "").replace(" ", ""))
    if hp is not None:
        toks.append(f"hp{hp}")
    if fx is not None:
        toks.append(f"fx{fx}")
    if js is not None:
        toks.append(f"js{js}")
    if not toks:
        return []
    ix = _open_index()
    qp = QueryParser("template", schema=ix.schema)
    q = qp.parse(" ".join(toks))
    with ix.searcher() as s:
        hits = s.search(q, limit=k)
        return [(h["stage_id"], h["doc_id"], h["factor"], h["difficulty"], h["stage"], h.score) for h in hits]


_COUNTER_PROFILES = None


def _counter_profiles():
    global _COUNTER_PROFILES
    if _COUNTER_PROFILES is None:
        fp = f"{HERE}/counter_profiles.json"
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                _COUNTER_PROFILES = json.load(f)
        else:
            _COUNTER_PROFILES = {}
    return _COUNTER_PROFILES


def _counter_query(stage_id, k=20):
    """R4：克制面相似召回（Jaccard 与覆盖率混合打分）。"""
    prof = _counter_profiles()
    q = prof.get(stage_id)
    if not q or not q.get("counter"):
        return []
    qset = set(q["counter"])
    scored = []
    for sid, p in prof.items():
        if sid == stage_id:
            continue
        c = p.get("counter") or []
        if not c:
            continue
        cset = set(c)
        inter = len(qset & cset)
        if inter == 0:
            continue
        jac = inter / len(qset | cset)
        cov = inter / len(qset)
        score = round(0.5 * jac + 0.5 * cov, 4)
        scored.append((sid, p["doc_id"], p["factor"], p["difficulty"], p["stage"], score))
    scored.sort(key=lambda x: -x[5])
    return scored[:k]


_MECH_MAP = None


def _mech_map():
    global _MECH_MAP
    if _MECH_MAP is None:
        fp = f"{HERE}/mech_map.json"
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                _MECH_MAP = json.load(f)
        else:
            _MECH_MAP = {}
    return _MECH_MAP


def _hard_gate_query(hard_slugs, k=20):
    """R_hard：硬门命中路由，按命中率降序。"""
    if not hard_slugs:
        return []
    mm = _mech_map()
    hs = set(hard_slugs)
    scored = []
    for sid, p in mm.items():
        hit = len(hs & set(p.get("mech") or []))
        if hit == 0:
            continue
        cov = round(hit / len(hs), 4)
        scored.append((sid, p["doc_id"], p["factor"], p["difficulty"], p["stage"], cov))
    scored.sort(key=lambda x: -x[5])
    return scored[:k]


def rrf(route_ranked, weights, k=60):
    scores = collections.defaultdict(float)
    meta = {}
    for (items, w) in zip(route_ranked, weights):
        for rank, it in enumerate(items):
            key = it[0]  # stage_id
            scores[key] += w / (60 + rank + 1)
            meta[key] = it  # (stage_id, doc_id, factor, difficulty, stage, orig_score)
    out = []
    for key in sorted(scores, key=lambda x: -scores[x]):
        it = meta[key]
        out.append({"stage_id": it[0], "doc_id": it[1], "factor": it[2],
                    "difficulty": it[3], "stage": it[4], "score": round(scores[key], 4)})
    return out[:k]


def _stage_card(doc_id, factor, difficulty, stage):
    d = load_doc(factor, difficulty)
    if not d:
        return None
    s = next((x for x in d["stages"] if x.get("stage") == stage), None)
    if not s:
        return None
    return {"doc_id": doc_id, "factor": factor, "difficulty": difficulty,
            "stage": stage, "stage_card": s}


def _cold_start(position, difficulty, top=5):
    with open(f"{HERE}/stats.json", encoding="utf-8") as f:
        st = json.load(f)
    hints = st["cold_start_hints"].get(str(position), [])
    by_pd = st["by_position_difficulty"].get(str((position, difficulty)), {})
    pd = [(m, v["pct"]) for m, v in sorted(by_pd.items(), key=lambda x: -x[1]["pct"])[:top]]
    return {"tag": "冷启动·先验推断（该关无实测特性/打法）",
            "position": position, "difficulty": difficulty,
            "all_difficulty_top": hints, "this_difficulty_top": pd,
            "default_mechs": st["default_mechs"]}


def plan(factor, difficulty, stage_num, k=8, weights=(1.0, 1.0, 0.5, 2.0)):
    """入口。返回 dict。weights=(R2机制, R4克制, R3数值, R_hard硬门)。"""
    d = load_doc(factor, difficulty)
    if not d:
        return {"error": f"未找到 {factor}#{difficulty} 的 SSOT 文档"}

    qs = next((s for s in d["stages"] if s.get("stage") == stage_num), None)
    if not qs:
        return {"error": f"{factor}#{difficulty} 无第 {stage_num} 关"}

    resp = {
        "query": {"factor": factor, "difficulty": difficulty, "stage": stage_num},
        "r1_exact": d,                       # 整块必召回
        "query_mech": [M.SLUG2CI[x] for x in (qs.get("mech") or [])],
        "query_hard_gates": [M.SLUG2CI[x] for x in (qs.get("mech") or []) if x in HARD],
    }
    if d.get("ban"):
        resp["banned"] = d["ban"]

    mech_slugs = qs.get("mech") or []
    hard_slugs = [x for x in mech_slugs if x in HARD]
    r2 = _mech_query(mech_slugs, k=20)
    r4 = _counter_query(f"{factor}#{difficulty}#{stage_num}", k=20)
    r5 = _hard_gate_query(hard_slugs, k=20)
    fx, js = None, None
    tr = qs.get("traits") or ""
    mfx = re.search(r"(\d+)\s*固伤", tr)
    mjs = re.search(r"减伤\s*([\d.]+)\s*%", tr)
    fx = int(mfx.group(1)) if mfx else None
    js = mjs.group(1) if mjs else None
    r3 = _template_query(qs.get("boss_type"), qs.get("boss_hp"), fx, js, k=20)

    self_sid = f"{factor}#{difficulty}#{stage_num}"
    r2 = [x for x in r2 if x[0] != self_sid]
    r3 = [x for x in r3 if x[0] != self_sid]
    r5 = [x for x in r5 if x[0] != self_sid]

    merged = rrf([r2, r4, r3, r5], weights, k=60)
    sim = []
    for item in merged:
        card = _stage_card(item["doc_id"], item["factor"], item["difficulty"], item["stage"])
        if not card:
            continue
        cmech = set(card["stage_card"].get("mech") or [])
        card["score"] = item["score"]
        card["covers"] = [M.SLUG2CI[x] for x in (set(mech_slugs) & cmech)]
        card["gaps"] = [M.SLUG2CI[x] for x in (set(mech_slugs) - cmech) if x in HARD]
        sim.append(card)

    sim = sim[:k]

    resp["similar"] = sim
    if not sim and not (qs.get("strategies")):
        resp["cold_start"] = _cold_start(stage_num, difficulty)
    return resp


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("factor")
    ap.add_argument("difficulty")
    ap.add_argument("stage", type=int)
    args = ap.parse_args()
    r = plan(args.factor, args.difficulty, args.stage)
    print(json.dumps({k: r[k] for k in (
        "query_mech", "query_hard_gates", "banned") if k in r}, ensure_ascii=False, indent=1))
    print("--- 相似关 top ---")
    for s in r.get("similar", []):
        print(f"{s['factor']}#{s['difficulty']}#{s['stage']}  score={s['score']}  "
              f"覆盖={s['covers']} 缺口={s['gaps']}")
        # strategies 已是对象数组 {text, source, plan, pets, why}，预览取第一个的 text
        strats = s["stage_card"].get("strategies") or []
        first = "无攻略"
        if strats:
            first = strats[0].get("text") if isinstance(strats[0], dict) else str(strats[0])
        print("   ", str(first)[:80])