import json, glob, os, re, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_records import _summary

REC = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\battle-records"
battles = []
for f in sorted(glob.glob(os.path.join(REC, "battle-*.json"))):
    report = json.load(open(f, encoding="utf-8"))
    # 跳过占位/手写样例（无 result 字段、catch_time=0 之类，非真实战斗记录）
    if "result" not in report:
        continue
    m = re.search(r"battle-(\d+)\.json$", os.path.basename(f))
    ts = int(m.group(1)) if m else report.get("ts") or 0
    report = dict(report)
    report["time"] = ts
    report.setdefault("ts", ts)
    battles.append(_summary(report))

battles.sort(key=lambda b: b.get("ts", 0), reverse=True)
with open(os.path.join(REC, "index.json"), "w", encoding="utf-8") as fh:
    json.dump({"battles": battles[:200]}, fh, ensure_ascii=False, indent=2)

for b in battles:
    print(f"{b['title']} · {b['winner']} · 第{b['stage']}关  (id={b['id']})")