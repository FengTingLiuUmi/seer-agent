# -*- coding: utf-8 -*-
"""合并 biliextract/factor-*.json → factors-bili.json（按 factor 合并，均为地狱档）。
B站多帖同因子去重：stages 按关号并集，保留 boss_type/boss_hp/traits/strategy/pets/source。
"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
BD = f"{HERE}/biliextract"

merged = {}
for fp in sorted(glob.glob(f"{BD}/factor-*.json")):
    try:
        it = json.load(open(fp, encoding="utf-8"))
    except Exception as e:
        print("跳过坏文件", fp, e)
        continue
    fac = (it.get("factor") or "").strip()
    if not fac:
        continue
    diff = (it.get("difficulty") or "地狱").strip()
    if not (it.get("stages") or []):
        print("跳过无关卡文件", fp, "|", (it.get("note") or "")[:40])
        continue
    e = merged.setdefault(fac, {"factor": fac, "difficulty": diff, "source": set(), "stages": {}, "note": ""})
    if it.get("source"):
        e["source"].add(str(it["source"]))
    for st in it.get("stages") or []:
        n = st.get("stage")
        if n is None:
            continue
        n = int(n)
        s = e["stages"].setdefault(n, {"stage": n, "pets": [], "strategies": [], "traits": []})
        for k in ("boss_type", "boss_hp"):
            v = st.get(k)
            if v not in (None, "") and k not in s:
                s[k] = v
        if st.get("traits"):
            s["traits"].append(str(st["traits"]))
        if st.get("strategy"):
            s["strategies"].append(str(st["strategy"]))
        for p in st.get("pets") or []:
            if p and p not in s["pets"]:
                s["pets"].append(str(p))
    if it.get("note"):
        e["note"] = str(it["note"])

out = []
for e in merged.values():
    e["source"] = sorted(e["source"])
    e["stages"] = [e["stages"][n] for n in sorted(e["stages"])]
    for s in e["stages"]:
        if s.get("traits"):
            s["traits"] = "; ".join(s["traits"])
        else:
            s.pop("traits", None)
        for k in ("pets", "strategies"):
            if not s.get(k):
                s.pop(k, None)
    if not e["source"]:
        e.pop("source", None)
    if not e["note"]:
        e.pop("note", None)
    out.append(e)
out.sort(key=lambda x: x["factor"])

with open(f"{HERE}/factors-bili.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

n = len(out)
with_traits = sum(1 for e in out if any("traits" in s for s in e["stages"]))
with_pets = sum(1 for e in out if any("pets" in s for s in e["stages"]))
empty = sum(1 for e in out if not e["stages"])
print(f"B站因子数 = {n}；有特性 = {with_traits}；有攻略 = {with_pets}；空 = {empty}")
print("写出", f"{HERE}/factors-bili.json")