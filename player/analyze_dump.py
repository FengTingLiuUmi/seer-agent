# -*- coding: utf-8 -*-
"""诊断 full.json 的普通仓库(2303)解析质量，避免把 16B 步长错位产生的假条目灌进缓存。"""
import os
import json
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "dump")


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


data = json.loads(read_text(os.path.join(DUMP, "full.json")))
for key in ("bag", "elite", "normal"):
    arr = data.get(key, [])
    sps = {e["species_id"] for e in arr}
    cts = [e["catch_time"] for e in arr]
    dup = [c for c, n in collections.Counter(cts).items() if n > 1]
    lv = collections.Counter(e.get("level") for e in arr)
    print(f"{key}: n={len(arr)}  物种数={len(sps)}  唯一catch={len(set(cts))}  重复catch={len(dup)}")
    if key == "normal":
        print("  level 分布 top:", lv.most_common(6))
        print("  样例:", json.dumps(arr[:8], ensure_ascii=False))

# 三处合计去重（按 catch_time 全局唯一）
all_ct = [e["catch_time"] for e in data.get("bag", []) + data.get("elite", []) + data.get("normal", [])]
dup_all = [c for c, n in collections.Counter(all_ct).items() if n > 1]
print(f"\n三处合计条目={len(all_ct)}  全局唯一个体(catch_time)={len(set(all_ct))}  跨仓重复catch={len(dup_all)}")