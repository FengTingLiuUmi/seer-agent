# -*- coding: utf-8 -*-
"""把 factors-final.json 拆成 SSOT 文档 kb/docs/<factor>/<difficulty>.json。
- 主键 doc_id = "因子#难度"；一份文件一个主键，含该因子该难度全部关卡 + 每关多打法并列。
- 每关附加派生字段 mech（机制标签集合，来自 mechanisms.extract）与 apex（第5关本体标识）。
- why 从 factors-why.json 按 (因子,难度,关号) 并入。
- 产出同目录 docs/catalog.json（doc_id → 路径/关数），供索引/统计/MCP 枚举。
幂等：可随时重跑；不会手改这里的派生字段之外的东西。
运行：PYTHONUTF8=1 python split_docs.py
"""
import os, json, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, HERE)
import mechanisms as M  # noqa: E402
import refactor_strategies as RS  # noqa: E402

SCRAPE = os.path.join(HERE, "..", "scrape").replace("\\", "/")
DOCS = os.path.join(HERE, "docs").replace("\\", "/")

with open(f"{SCRAPE}/factors-final.json", encoding="utf-8") as f:
    FINAL = json.load(f)
WHY = []
if os.path.exists(f"{SCRAPE}/factors-why.json"):
    with open(f"{SCRAPE}/factors-why.json", encoding="utf-8") as f:
        WHY = json.load(f)

why_by = {}
for w in WHY:
    if isinstance(w, dict) and (w.get("whys") or []):
        why_by[((w.get("factor") or "").replace("·", "").replace(" ", ""), w.get("difficulty") or "地狱")] = \
            {x.get("stage"): x.get("why") for x in w["whys"] if x.get("stage") and x.get("why")}

# SeerAPI 权威：每关 Boss 是哪只精灵（factor-boss-design.json，由 ontology/fetch_boss_pets.py 产出）
BOSS_DESIGN = {}
_bd = f"{SCRAPE}/factor-boss-design.json"
if os.path.exists(_bd):
    with open(_bd, encoding="utf-8") as f:
        BOSS_DESIGN = json.load(f).get("factors", {})

_DIFF_KEY = {"地狱": "hard", "困难": "normal", "简单": "easy"}


def _scale_for(difficulty, n):
    """Boss 数值缩放倍率 (双攻, 双防)。地狱为社区实测通用值；困难/简单待补 → None（宁缺毋滥）。"""
    if difficulty == "地狱":
        if n in (1, 2):
            return (6.0, 1.2)
        if n in (3, 4, 5):
            return (6.5, 1.5)
    return (None, None)


def norm(s):
    return re.sub(r"[\s·]", "", str(s))


def make_doc(factor, difficulty, stages, ban, tids, note):
    out_stages = []
    for s in sorted(stages, key=lambda x: (x.get("stage") or 0)):
        n = s.get("stage")
        why_key = whey = None
        whys = why_by.get((norm(factor), difficulty)) or {}
        whey = whys.get(n)
        doc_stage = {
            "stage": n,
            "apex": (n == 5),
        }
        # SeerAPI 权威：Boss 本体（物种）+ 数值缩放倍率
        bp = (BOSS_DESIGN.get(factor) or {}).get("stages", {}).get(_DIFF_KEY.get(difficulty, difficulty), {}).get(str(n))
        if bp and bp.get("boss_pet_id"):
            doc_stage["boss_pet_id"] = bp["boss_pet_id"]
            if bp.get("is_single_pet") is not None:
                doc_stage["boss_is_single_pet"] = bool(bp["is_single_pet"])
        atk_scale, def_scale = _scale_for(difficulty, n)
        if atk_scale is not None:
            doc_stage["boss_atk_scale"] = atk_scale
        if def_scale is not None:
            doc_stage["boss_def_scale"] = def_scale
        if s.get("boss_type"):
            doc_stage["boss_type"] = s["boss_type"]
        if s.get("boss_hp"):
            doc_stage["boss_hp"] = int(s["boss_hp"])
        if s.get("traits"):
            doc_stage["traits"] = s["traits"]
            doc_stage["mech"] = M.extract(s["traits"])
        if s.get("strategies"):
            doc_stage["strategies"] = s["strategies"]
        if s.get("pets"):
            doc_stage["pets"] = s["pets"]
        if whey:
            doc_stage["why"] = whey
        out_stages.append(doc_stage)

    doc = {
        "doc_id": f"{factor}#{difficulty}",
        "factor": factor,
        "difficulty": difficulty,
        "stages": out_stages,
    }
    if ban:
        doc["ban"] = ban
    if tids:
        doc["tids"] = tids
    if note:
        doc["note"] = note
    return doc


# 按 (因子 × 难度) 聚合
groups = {}
for e in FINAL:
    fac = e["factor"]
    by_d = {}
    for s in e.get("stages", []):
        by_d.setdefault(s.get("difficulty"), []).append(s)
    for dif, sts in by_d.items():
        groups[(fac, dif)] = dict(factor=fac, difficulty=dif, stages=sts,
                                  ban=e.get("ban", []), tids=e.get("tids", []), note=e.get("note", ""))

if os.path.exists(DOCS):
    import shutil
    shutil.rmtree(DOCS)
os.makedirs(DOCS)

catalog = []
for (fac, dif), g in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
    doc = make_doc(fac, dif, g["stages"], g["ban"], g["tids"], g["note"])
    doc, _ = RS.apply(doc)  # strategies → 对象格式 + source_urls
    d = os.path.join(DOCS, fac)
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, f"{dif}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    catalog.append({"doc_id": doc["doc_id"], "factor": fac, "difficulty": dif,
                    "path": os.path.relpath(fp, HERE).replace("\\", "/"), "n_stages": len(doc["stages"])})

with open(f"{DOCS}/catalog.json", "w", encoding="utf-8") as f:
    json.dump(catalog, f, ensure_ascii=False, indent=1)

n_stages = sum(c["n_stages"] for c in catalog)
print(f"docs = {len(catalog)} 份（因子×难度），关卡 = {n_stages}")
print("写出", DOCS)