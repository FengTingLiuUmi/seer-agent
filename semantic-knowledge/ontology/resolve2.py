# -*- coding: utf-8 -*-
"""解析更多常用 PVE 精灵的 id（按名字搜，dump 候选到 resolve2.txt）。"""
import json, urllib.request, urllib.parse, os
BASE = "https://api.seerapi.com/v1/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "resolve2.txt")

def search(resource, name, limit=15):
    q = urllib.parse.urlencode({"name": name, "limit": limit, "expand": "true"})
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}{resource}?{q}", headers={"User-Agent":"r"}), timeout=30) as r:
        return json.load(r).get("results", [])

terms = ["哈莫雷特", "谱尼", "波克尔", "典韦", "斯克鲁恩", "泰坦", "张飞",
         "魔钰", "卡莎", "幻境", "西塔伦", "草王", "村长", "毁灭机甲", "地王"]
lines = []
for t in terms:
    lines.append(f"===== name={t} =====")
    try:
        items = search("pet", t)
        if not items:
            lines.append("  (none)")
        for it in items:
            bs = it.get("base_stats") or {}
            lines.append(f"  id={it.get('id')} name={it.get('name')} total={bs.get('total')}")
    except Exception as e:
        lines.append(f"  FAIL {e}")
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("done ->", OUT)