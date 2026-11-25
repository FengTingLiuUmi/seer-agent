# -*- coding: utf-8 -*-
"""从 SSOT docs 派生机制占比统计 kb/stats.json。
- 默认机制：df = 出现关数/有特性关数 > 50%，自动判入 default_mechs，统计里剔除（必先/封属/固伤等噪音）。
- 维度：第N关 × 难度 × Boss属性 的机制出现占比，供『新关无攻略』冷启动当先验。
幂等派生，随 docs 重建，不手改。
运行：PYTHONUTF8=1 python build_stats.py
"""
import os, json, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
DOCS = f"{HERE}/docs"

docs = []
for fp in sorted(glob.glob(f"{DOCS}/*/*.json")):
    if fp.endswith("catalog.json"):
        continue
    with open(fp, encoding="utf-8") as f:
        docs.append(json.load(f))

stages = [(d, s) for d in docs for s in d.get("stages", []) if s.get("mech")]
N = len(stages)

df = collections.Counter()
for d, s in stages:
    for m in set(s["mech"]):
        df[m] += 1

default_mechs = sorted(m for m, c in df.items() if c / N > 0.5)


def pct(cells_total, cells_with):
    return None


def table_for(keyfn):
    """cells[key] -> Counter(mech)。返回 {key: {slug: {'n':, 'total':, 'pct':}}}（剔除默认）。"""
    cells = {}
    totals = {}
    for d, s in stages:
        k = keyfn(d, s)
        if k is None:
            continue
        cells.setdefault(k, collections.Counter())
        totals[k] = totals.get(k, 0) + 1
        for m in set(s["mech"]) - set(default_mechs):
            cells[k][m] += 1
    out = {}
    for k in sorted(cells, key=lambda x: str(x)):
        c = cells[k]
        out[str(k)] = {m: {"n": v, "total": totals[k], "pct": round(v / totals[k] * 100, 1)}
                       for m, v in sorted(c.items(), key=lambda x: -x[1])}
    return out


stats = {
    "built_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    "num_docs": len(docs),
    "num_stages_with_mech": N,
    "default_mechs": default_mechs,
    "df": {m: {"n": c, "df_pct": round(c / N * 100, 1)} for m, c in sorted(df.items(), key=lambda x: -x[1])},
    "by_position": table_for(lambda d, s: s["stage"]),
    "by_position_difficulty": table_for(lambda d, s: (s["stage"], d["difficulty"])),
    "by_type_position": table_for(lambda d, s: (s.get("boss_type") or "?", s["stage"])),
}

# 冷启动速览：每关 top-3 非默认机制
top = {}
for pos in range(1, 7):
    base = stats["by_position"].get(str(pos), {})
    top[str(pos)] = [(m, v["pct"]) for m, v in sorted(base.items(), key=lambda x: -x[1]["pct"])[:3]]
stats["cold_start_hints"] = top

with open(f"{HERE}/stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=1)
print(f"stages_with_mech = {N}")
print(f"default_mechs(df>50%) = {default_mechs}")
print("cold_start_hints(每关 top 非默认机制):")
for k, v in top.items():
    print(f"  第{k}关: {v}")
print("写出", f"{HERE}/stats.json")