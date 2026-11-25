# -*- coding: utf-8 -*-
"""从三档 thread 索引抽标题，按难度分组去重输出，便于人工/子代理筛因子名。"""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

diff = {"9": "简单", "10": "困难", "11": "地狱"}
rows = []
for t in ["9", "10", "11"]:
    p = f"{HERE}/threads-{t}.json"
    if not os.path.exists(p):
        continue
    for it in json.load(open(p, encoding="utf-8")):
        rows.append((diff[t], it["tid"], it["title"].strip()))

print("总标题(含重复因子名) =", len(rows))
out = f"{HERE}/titles-all.txt"
with open(out, "w", encoding="utf-8") as f:
    for d, tid, title in rows:
        f.write(f"[{d}] {tid}\t{title}\n")
print("已写", out)

uniq = {}
for d, tid, title in rows:
    uniq.setdefault(title, []).append((d, tid))
print("去重标题数 =", len(uniq))

# 多因子合并帖：标题里出现顿号/、的，拷出来单独看
multi = [t for t in uniq if ("、" in t or "，" in t or "合集" in t)]
print(f"疑似多因子/合集标题 = {len(multi)}")
out2 = f"{HERE}/titles-multi.txt"
with open(out2, "w", encoding="utf-8") as f:
    for t in sorted(multi):
        f.write(t + "\n")
print("已写", out2)