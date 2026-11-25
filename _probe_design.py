# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
# 错误码
print("== error_code 1905010 ==")
print(json.dumps(p.get("error_code", 1905010, fields=["name", "desc"]), ensure_ascii=False, default=str))
# factor_design 130
print("== factor_design 130 ==")
d = p.get("factor_design", 130)
if d:
    keep = {k: d.get(k) for k in ("id", "name", "progress_value", "time_value", "fail_times", "target") if k in d}
    print(json.dumps(keep, ensure_ascii=False, default=str))
    for lvl in d.get("difficulties") or []:
        print("  difficulty:", json.dumps(lvl, ensure_ascii=False, default=str)[:500])