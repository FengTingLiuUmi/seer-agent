# -*- coding: utf-8 -*-
"""分析 main_full_dump.json：进度/锁定 + 按 species 聚合的完整个体清单。"""
import json, sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

_raw = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\data\main_full_dump.json").read_bytes()
for _enc in ("utf-8-sig", "utf-16", "utf-8"):
    try:
        dump = json.loads(_raw.decode(_enc))
        break
    except (UnicodeDecodeError, json.JSONDecodeError):
        continue

print("uid:", dump.get("uid"))
print("瓦坎 forever(progress/time/fail):", dump.get("vakan_forever_progress_time_fail"))
print("瓦坎 锁定槽 303304..303327:", dump.get("vakan_locked_slots_303304_327"))
print("bag_count(43706头计数):", dump.get("bag_count"), " bag行:", len(dump.get("bag", [])))
print("elite:", dump.get("elite_count"), " normal:", dump.get("normal_count"))
print()

# 聚合 species -> individuals
species = {}
def add(row, store):
    sp = row["species_id"]
    species.setdefault(sp, {"name": row.get("name") or str(sp), "sp": sp, "inds": []})
    species[sp]["inds"].append({"store": store, "catch": row.get("catch_time"), "flag": row.get("flag"), "lv": row.get("level")})

for r in dump.get("bag", []):
    add(r, "bag")
for r in dump.get("elite", []):
    add(r, "elite")
for r in dump.get("normal", []):
    add(r, "normal")

rows = sorted(species.values(), key=lambda x: x["name"])
print("=== 全 species 聚合（按名排序，共 %d 个物种）===" % len(rows))
for s in rows:
    inds = s["inds"]
    store_sum = {}
    for i in inds:
        key = i["store"]
        store_sum[key] = store_sum.get(key, 0) + 1
    lvs = sorted({i["lv"] for i in inds if i.get("lv") is not None})
    print(f'{s["sp"]:5d}  {s["name"]:<12s} 数={len(inds)} 分布={store_sum} 等级={lvs}')