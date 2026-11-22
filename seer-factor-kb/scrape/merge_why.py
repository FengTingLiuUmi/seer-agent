# -*- coding: utf-8 -*-
"""合并 whys/factor-*.json → factors-why.json（数组）。"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
out = []
for fp in sorted(glob.glob(f"{HERE}/whys/factor-*.json") + glob.glob(f"{HERE}/whys-kunnan/*.json")):
    try:
        it = json.load(open(fp, encoding="utf-8"))
    except Exception as e:
        print("坏文件", fp, e)
        continue
    if not (it.get("whys") or []):
        print("跳过无 why 的文件", fp)
        continue
    out.append(it)
with open(f"{HERE}/factors-why.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("why 因子数 =", len(out))