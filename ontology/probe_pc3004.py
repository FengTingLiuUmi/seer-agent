# -*- coding: utf-8 -*-
import json, urllib.request, time, os
BASE = "https://api.seerapi.com/v1/"
def gj(u, tries=4):
    last=None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"r"}), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last=e; time.sleep(1)
    raise last
try:
    d = gj(f"{BASE}pet_class/3004")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"pc3004.json"),"w",encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    print("keys:", list(d.keys()))
    for k,v in d.items():
        if k in ("id","name","desc"):
            print(k, "=", v)
        elif isinstance(v,list):
            print(k, "= list len", len(v), "sample", json.dumps(v[:8], ensure_ascii=False)[:600])
        elif isinstance(v,dict):
            print(k, "=", json.dumps(v, ensure_ascii=False)[:200])
        else:
            print(k, "=", v)
except Exception as e:
    print("FAIL", type(e).__name__, e)