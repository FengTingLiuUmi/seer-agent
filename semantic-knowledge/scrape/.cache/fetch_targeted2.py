import json, subprocess, os, io

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "targeted2.txt")

def api(args):
    p = subprocess.run(["seerapi"] + args, capture_output=True)
    for enc in ("utf-8", "gbk"):
        try:
            return json.loads(p.stdout.decode(enc))
        except Exception:
            continue
    return None

skills = [
 # 圣灵谱尼
 11000, 18006, 17912, 24319, 31140, 31141, 31142, 31143, 25678, 25679, 20500, 10999, 10998,
 # 艾欧丽娅
 30906, 30907, 30908, 30909, 30910, 30928, 30929, 30930, 31114, 31115, 31116, 31117, 25561, 25562, 25563, 25572, 25573, 20618,
]

out = io.open(OUT, "w", encoding="utf-8")
for sid in skills:
    d = api(["get", "skill", str(sid)])
    if not d:
        out.write("SKILL %s NOTFOUND\n" % sid); continue
    eff = "; ".join(e.get("info") or "" for e in (d.get("skill_effect") or []))
    out.write("SKILL %s %s pow=%s pp=%s prio=%s hit=%s cat=%s type=%s | %s\n" % (
        sid, d.get("name"), d.get("power"), d.get("max_pp"), d.get("priority"),
        d.get("must_hit"), (d.get("category") or {}).get("id"), (d.get("type") or {}).get("id"), eff))
out.close()
print("done")