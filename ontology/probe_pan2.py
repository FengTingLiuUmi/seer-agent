# -*- coding: utf-8 -*-
import json, urllib.request, os
BASE = "https://api.seerapi.com/v1/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "resolve-pan2.txt")
def gj(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"r"}), timeout=30) as r:
        return json.load(r)
lines=[]
for url in [f"{BASE}pet_class/3004", f"{BASE}soulmark/1569"]:
    try:
        d = gj(url)
        lines.append(f"===== {url} =====")
        for k,v in d.items():
            if isinstance(v,(dict,list)):
                lines.append(f"  {k} = {json.dumps(v, ensure_ascii=False)[:500]}")
            else:
                lines.append(f"  {k} = {v}")
    except Exception as e:
        lines.append(f"===== {url} FAIL {e} =====")
with open(OUT,"w",encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("done ->", OUT)