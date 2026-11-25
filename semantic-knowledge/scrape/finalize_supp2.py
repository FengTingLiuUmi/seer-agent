# -*- coding: utf-8 -*-
"""给 pets-supplement2.json 补 type（走本体 TypeCombination 的 seerapiId 映射），
并统计噪声/未解析。输出仍是 pets-supplement2.json（可重复执行）。
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

combo = json.load(open(f"{HERE}/combo-map.json", encoding="utf-8"))
idx = {str(p["id"]): p for p in json.load(open(f"{HERE}/pets-index.json", encoding="utf-8"))}
sup = json.load(open(f"{HERE}/pets-supplement2.json", encoding="utf-8"))

missing_combo = []
for p in sup["pets"]:
    cid = str((idx[p["seerapiId"]].get("type") or {}).get("id"))
    elems = combo.get(cid)
    if elems:
        p["type"] = elems
    else:
        p["type"] = []
        missing_combo.append((p["name"], p["seerapiId"], cid))
    p.setdefault("role", "")

sup["noise"] = sup.get("noise") or []
sup["unresolved"] = sup.get("noise_or_unresolved") or []
json.dump(sup, open(f"{HERE}/pets-supplement2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"pets = {len(sup['pets'])}")
print(f"  type 已填 = {sum(1 for p in sup['pets'] if p['type'])}")
print(f"  type 缺失 = {len(missing_combo)} {missing_combo[:5]}")
print(f"  unresolved/noise = {len(sup['unresolved'])}")
print("  ", sup["unresolved"])