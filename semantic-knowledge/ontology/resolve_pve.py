# -*- coding: utf-8 -*-
"""解析常用 PVE 精灵的正确 ID/形态（解决昵称歧义）。结果写 resolve-pve.txt（UTF-8）。"""
import json, urllib.request, urllib.parse, os

BASE = "https://api.seerapi.com/v1/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "resolve-pve.txt")


def gj(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "res"}), timeout=30) as r:
        return json.load(r)


def search(resource, name, limit=20, expand=True):
    q = urllib.parse.urlencode({"name": name, "limit": limit, "expand": "true"})
    d = gj(f"{BASE}{resource}?{q}")
    return d.get("results", [])


lines = []
def dump(title, items):
    lines.append(f"===== {title} =====")
    if not items:
        lines.append("  (none)")
        return
    for it in items[:20]:
        nm = it.get("name")
        bs = it.get("base_stats") or {}
        tot = bs.get("total")
        lines.append(f"  id={it.get('id')} name={nm} total={tot}")

for term in ["潘多克斯", "潘克多斯", "潘", "星光", "鲁斯王", "魔焰猩猩", "猩猩"]:
    try:
        dump(f"pet?name={term}", search("pet", term))
    except Exception as e:
        lines.append(f"===== pet?name={term} FAIL {e} =====")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("done ->", OUT)