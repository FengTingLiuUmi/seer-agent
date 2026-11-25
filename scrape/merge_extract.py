# -*- coding: utf-8 -*-
"""合并 factor-extract/batch-*.json → factors-extracted.json（按 factor×难度 去重）。
多线程/多帖对同一因子的部分抽取合并：stages 按关号合并策略/阵容/配置/特性/属性。
"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
EXTD = f"{HERE}/factor-extract"

merged = {}
for fp in sorted(glob.glob(f"{EXTD}/batch-*.json")):
    try:
        data = json.load(open(fp, encoding="utf-8"))
    except Exception as e:
        print("跳过坏文件", fp, e)
        continue
    for it in data.get("items", []):
        fac = (it.get("factor") or "").strip()
        dif = (it.get("difficulty") or "").strip()
        if not fac:
            continue
        key = (fac, dif)
        e = merged.setdefault(key, {"factor": fac, "difficulty": dif,
                                    "tids": [], "ban": [], "stages": {}, "note": ""})
        tid = it.get("tid")
        if tid is not None:
            e["tids"].append(int(tid))
        for b in it.get("ban") or []:
            if b and b not in e["ban"]:
                e["ban"].append(b)
        for st in it.get("stages") or []:
            n = st.get("stage")
            if n is None:
                continue
            n = int(n)
            s = e["stages"].setdefault(n, {"stage": n, "pets": [], "strategies": [],
                                           "config": [], "boss_type": "", "boss_hp": None, "traits": []})
            for k in ("boss_type", "boss_hp"):
                v = st.get(k)
                if v not in (None, "") and not s[k]:
                    s[k] = v
            if st.get("traits"):
                s["traits"].append(str(st["traits"]))
            if st.get("strategy"):
                s["strategies"].append(str(st["strategy"]))
            for p in st.get("pets") or []:
                if p and p not in s["pets"]:
                    s["pets"].append(str(p))
            if st.get("config"):
                s["config"].append(str(st["config"]))
        if it.get("note") and not e["note"]:
            e["note"] = str(it["note"])

out = []
for e in merged.values():
    e["tids"] = sorted(set(e["tids"]))
    e["stages"] = [e["stages"][n] for n in sorted(e["stages"])]
    del_keys = []
    for s in e["stages"]:
        if not s["pets"]:
            s.pop("pets", None)
        if not s["strategies"]:
            s.pop("strategies", None)
        if not s["config"]:
            s.pop("config", None)
        if not s["boss_type"]:
            s.pop("boss_type", None)
        if s["boss_hp"] is None:
            s.pop("boss_hp", None)
        if s["traits"]:
            s["traits"] = "; ".join(s["traits"])
        else:
            s.pop("traits", None)
    if not e["ban"]:
        e.pop("ban", None)
    if not e["note"]:
        e.pop("note", None)
    out.append(e)

out.sort(key=lambda x: (x["difficulty"], x["factor"]))
with open(f"{HERE}/factors-extracted.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

n = len(out)
with_traits = sum(1 for e in out if any("traits" in s for s in e["stages"]))
with_pets = sum(1 for e in out if any("pets" in s for s in e["stages"]))
empty = sum(1 for e in out if not e["stages"])
print(f"factor×难度 条目 = {n}")
print(f"  有 boss 特性 = {with_traits}，有攻略/阵容 = {with_pets}，无任何关数据 = {empty}")
print("写出", f"{HERE}/factors-extracted.json")