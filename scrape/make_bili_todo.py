# -*- coding: utf-8 -*-
"""从 factors-roster.json 生成待 B站补特性的清单（默认只取 地狱 难度）。
输出 bili_todo.json = [{i, name, difficulties}]；并建 biliextract 输出目录。"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
roster = json.load(open(f"{HERE}/factors-roster.json", encoding="utf-8"))
outdir = f"{HERE}/biliextract"
os.makedirs(outdir, exist_ok=True)

todo = []
for f in roster["factors"]:
    if "地狱" not in f.get("difficulties", []):
        continue
    todo.append({"name": f["name"], "difficulties": f.get("difficulties", []), "tids": f.get("tids", [])})

todo.sort(key=lambda x: x["name"])
for i, t in enumerate(todo, 1):
    t["i"] = i

with open(f"{HERE}/bili_todo.json", "w", encoding="utf-8") as f:
    json.dump(todo, f, ensure_ascii=False, indent=0)
print(f"地狱因子待补特性 = {len(todo)}，写出 {HERE}/bili_todo.json")