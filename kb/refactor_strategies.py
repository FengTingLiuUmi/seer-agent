# -*- coding: utf-8 -*-
"""策略对象化：把一关的 strategies 从 list[str] 转成 list[{text,source,plan,pets,why}]。
- 只负责策略字段与 doc 级 source_urls；其余字段不动。
- 供 split_docs.py 调用（apply_source_level），也可独立跑全量（main）。
运行：PYTHONUTF8=1 python refactor_strategies.py [--limit N]
"""
import os, re, json, ast, sys

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SCRAPE = os.path.join(HERE, "..", "scrape").replace("\\", "/")

SRC_BILI = "bili"
SRC_FORUM = "forum"

ACTION_RE = re.compile(
    r"(单挑|站场|强攻|自爆|引爆|送死|送头|送buff|消强|吸强|偷强|断回合|弹伤|反伤|反弹|"
    r"补刀|嗑药|吃药|压血|控血|套盾|秒杀|收尾|收残|挂机|卡裸|赌翻|循环|磨血|回血|吸血|"
    r"翻倍|续航|抗住|保命|铺场|铺垫)")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def norm(s):
    return re.sub(r"[·.\s]", "", str(s))


def _load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


# --- 来源索引（模块级，供 split_docs 复用）---
_bili = _load(f"{SCRAPE}/factors-bili.json", [])
_forum = _load(f"{SCRAPE}/factors-extracted.json", [])
_whyf = _load(f"{SCRAPE}/factors-why.json", [])
ALIAS = {}
_ap = f"{SCRAPE}/factor_alias.json"
if os.path.exists(_ap):
    with open(_ap, encoding="utf-8") as f:
        _alias_map = json.load(f).get("map", {})
    for k, v in _alias_map.items():
        ALIAS[norm(k)] = norm(v)


def _ckey(name):
    n = norm(name)
    return ALIAS.get(n, n)


_bili_by = {}
_forum_by = {}
for e in _bili:
    _bili_by.setdefault((_ckey(e.get("factor")), e.get("difficulty")), []).append(e)
for e in _forum:
    _forum_by.setdefault((_ckey(e.get("factor")), e.get("difficulty")), []).append(e)

_why_by = {}
for w in _whyf:
    if not isinstance(w, dict):
        continue
    f = re.sub(r"[·\s]", "", str(w.get("factor") or ""))
    d = w.get("difficulty") or "地狱"
    _why_by.setdefault((f, d), {})
    for x in w.get("whys") or []:
        _why_by[(f, d)][x.get("stage")] = x.get("why")

# 逐策略 why 覆盖表（人工/agent 清洗过的那批）。
# 为什么需要它：策略 why 默认由 attrib_why() 从「关级 why」切句分配得来，
# 重跑 split_docs 会把清洗结果冲掉。这里按 (因子,难度,关号, plan归一) 精确覆盖，
# 文件不存在时行为与以前完全一致。
_swhy_by = {}
_swp = f"{SCRAPE}/factors-strategy-why.json"
if os.path.exists(_swp):
    _sw = _load(_swp, {})
    for k, stages in (_sw or {}).items():
        f, _, d = str(k).partition("|")
        for sn, plans in (stages or {}).items():
            for plan, why in (plans or {}).items():
                _swhy_by[(re.sub(r"[·\s]", "", f), d, int(sn), plan)] = why


def split_urls(src):
    urls = []
    for item in src or []:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parts = ast.literal_eval(s)
                if isinstance(parts, list):
                    for x in parts:
                        if str(x) not in urls:
                            urls.append(str(x))
                    continue
            except Exception:
                pass
        for u in URL_RE.findall(s):
            u = u.rstrip(".,;|")
            if u not in urls:
                urls.append(u)
    return urls


def split_methods(s):
    s = str(s).strip()
    parts = re.split(r"\s+/\s+", s)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        return [s] if s else []
    merged = []
    for p in parts:
        is_method = ("+" in p) or bool(ACTION_RE.search(p))
        if not merged:
            merged.append([p, is_method])
        else:
            prev, piv = merged[-1]
            if not is_method:
                merged[-1] = [prev + " / " + p, piv]
            else:
                merged.append([p, True])
    return [m[0] for m in merged]


def extract_pets(method_text, source_pets):
    out = []
    for p in source_pets:
        pp = str(p).strip()
        if not pp:
            continue
        core = re.sub(r"[（(].*?[)）]", "", pp)
        if pp in method_text or (core and core in method_text):
            out.append(pp)
    if any(k in method_text for k in ("自爆", "表姐", "守御八方")):
        for p in source_pets:
            if str(p) == "帝皇之御" and "帝皇之御" not in out:
                out.append("帝皇之御")
    return list(dict.fromkeys(out))


def _sentences(why):
    return [t.strip() for t in re.split(r"[。；;]", str(why or "")) if t.strip()]


def attrib_why(method_pets, stage_why):
    sents = _sentences(stage_why)
    if not sents:
        return ""
    if len(sents) == 1:
        return sents[0]
    hits = [x for x in sents if any(p and str(p) in x for p in method_pets)]
    return "；".join(dict.fromkeys(hits))


def _stages_map(entries):
    m = {}
    for e in entries:
        for st in e.get("stages", []):
            n = st.get("stage")
            if n is None:
                continue
            m.setdefault(n, {"strategies": [], "pets": []})
            for s_ in st.get("strategies") or []:
                if s_ not in m[n]["strategies"]:
                    m[n]["strategies"].append(s_)
            for p_ in st.get("pets") or []:
                if p_ not in m[n]["pets"]:
                    m[n]["pets"].append(p_)
    return m


def _canon_plan(t):
    return re.sub(r"\s+", "", t)


def apply(doc):
    """就地改写 doc 的每关 strategies 为对象格式 + 新增 doc 级 source_urls；返回 (doc, report_entries)。"""
    factor = doc["factor"]
    difficulty = doc["difficulty"]
    key = (_ckey(factor), difficulty)

    urls = []
    for be in _bili_by.get(key, []):
        urls += split_urls(be.get("source"))
    if urls:
        doc["source_urls"] = urls

    bstage = _stages_map(_bili_by.get(key, []))
    fstage = _stages_map(_forum_by.get(key, []))
    stage_whys = _why_by.get((re.sub(r"[·\s]", "", factor), difficulty), {})

    report = []
    for st in doc.get("stages", []):
        sn = st.get("stage")
        stage_why = st.get("why") or stage_whys.get(sn) or ""
        objs = []
        for src, smap in ((SRC_BILI, bstage), (SRC_FORUM, fstage)):
            sd = smap.get(sn)
            if not sd:
                continue
            for strategy_str in sd["strategies"]:
                for mt in split_methods(strategy_str):
                    pets = extract_pets(mt, sd["pets"])
                    why = attrib_why(pets, stage_why)
                    _ov = _swhy_by.get((re.sub(r"[·\s]", "", factor), difficulty, sn, _canon_plan(mt)))
                    if _ov:
                        why = _ov
                    objs.append({"text": mt, "source": src, "plan": mt, "pets": pets, "why": why})

        deduped = []
        for o in objs:
            ok = _canon_plan(o["plan"])
            hit = next((d for d in deduped if _canon_plan(d["plan"]) == ok), None)
            if hit is None:
                deduped.append(o)
            else:
                before = [hit["text"], o["text"]]
                hit["pets"] = list(dict.fromkeys(hit["pets"] + o["pets"]))
                hit["source"] = "+".join(sorted(set((hit["source"], o["source"]))))
                if not hit["why"] and o["why"]:
                    hit["why"] = o["why"]
                report.append({"factor": factor, "difficulty": difficulty, "stage_index": sn,
                               "before": before, "after": hit, "reason": "plan 归一相同，保守合并"})
        st["strategies"] = deduped
    return doc, report


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    DOCS = f"{HERE}/docs"
    files = sorted(x for x in __import__("glob").glob(f"{DOCS}/*/*.json")
                   if "catalog.json" not in x and "preview" not in x and "backup" not in x)
    report, stats = [], {"docs": 0, "stages": 0, "before": 0, "after": 0, "merged": 0}
    for fp in files:
        if limit is not None and stats["docs"] >= limit:
            break
        with open(fp, encoding="utf-8") as f:
            doc = json.load(f)
        nbefore = sum(len(s.get("strategies") or []) for s in doc.get("stages", []))
        doc, r = apply(doc)
        nafter = sum(len(s.get("strategies") or []) for s in doc.get("stages", []))
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        report += r
        stats["docs"] += 1
        stats["stages"] += len(doc.get("stages", []))
        stats["before"] += nbefore
        stats["after"] += nafter
        stats["merged"] += len(r)

    with open(f"{HERE}/strategy_dedup_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(f"{HERE}/strategy_refactor_notes.json", "w", encoding="utf-8") as f:
        json.dump({"stats": stats}, f, ensure_ascii=False, indent=1)
    print(f"docs={stats['docs']} stages={stats['stages']} strategies "
          f"{stats['before']}->{stats['after']} merged={stats['merged']}")


if __name__ == "__main__":
    main()