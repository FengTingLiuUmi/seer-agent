# -*- coding: utf-8 -*-
"""离线评估：检索层的自洽基线。
- 硬门覆盖率@k：对每个有特性的地狱关，plan 后 top-k 相似关里是否至少有一条「无硬门缺口」。
- 区分「带硬门」与「无硬门」查询（无硬门查询的覆盖是无信息的）。
不依赖 ranx，指标透明可核查。
运行：$env:PYTHONPATH="...\.pylibs"; PYTHONUTF8=1 python eval.py
"""
import os, json, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
import plan as P

HARD = P.HARD

queries = []
for fp in sorted(glob.glob(f"{HERE}/docs/*/*.json")):
    if fp.endswith("catalog.json"):
        continue
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("difficulty") != "地狱":
        continue
    for s in d.get("stages", []):
        if s.get("mech") and s.get("strategies"):
            queries.append((d["factor"], d["difficulty"], s["stage"], set(s["mech"])))

n = len(queries)
hard_n = sum(1 for *_, m in queries if m & HARD)
covered_all = covered_hard = 0
empty = 0
rets = []
for factor, dif, stage, mech in queries:
    r = P.plan(factor, dif, stage, k=8)
    sim = r.get("similar") or []
    rets.append(len(sim))
    if not sim:
        empty += 1
        continue
    hit = any(not c.get("gaps") for c in sim)
    covered_all += 1 if hit else 0
    if mech & HARD:
        covered_hard += 1 if hit else 0

print(f"查询(有特性+有攻略的地狱关) = {n}")
print(f"  其中带硬门 = {hard_n}")
print(f"硬门覆盖率@8（全查询） = {covered_all}/{n} = {covered_all/n*100:.1f}%")
print(f"硬门覆盖率@8（带硬门查询） = {covered_hard}/{hard_n} = {covered_hard/hard_n*100:.1f}%")
print(f"空召回(无相似关) = {empty}/{n}")
print(f"平均召回条数 = {sum(rets)/max(len(rets),1):.1f}")