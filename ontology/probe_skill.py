# -*- coding: utf-8 -*-
import json, urllib.request, os
BASE = "https://api.seerapi.com/v1/"
def gj(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"r"}), timeout=30) as r:
        return json.load(r)
lines=[]
for sid in [10611, 20265, 22295]:
    try:
        d = gj(f"{BASE}skill/{sid}")
        lines.append(f"===== skill/{sid} keys: {sorted(d.keys())} =====")
        for k in ("id","name","power","priority","category","type","effect_type","skill_category","kind","is_change","hit_rate"):
            if k in d:
                v = d[k]
                lines.append(f"  {k} = {json.dumps(v, ensure_ascii=False)[:200]}")
    except Exception as e:
        lines.append(f"skill/{sid} FAIL {e}")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"skill-fields.txt"),"w",encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("done")