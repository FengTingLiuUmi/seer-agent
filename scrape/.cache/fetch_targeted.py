import json, subprocess, os, io

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "targeted.txt")

def api(args):
    p = subprocess.run(["seerapi"] + args, capture_output=True)
    for enc in ("utf-8", "gbk"):
        try:
            return json.loads(p.stdout.decode(enc))
        except Exception:
            continue
    return None

skills = [
 # 伊芙莉莎 3844
 26682, 31156, 33192, 33193, 33194, 33195,
 # 艾莫莉萨 3573
 22870, 31822, 31823, 31824, 31825, 31826, 31827, 26019, 26020, 26021, 15250, 15247,
 # 六界帝神 3329
 30549, 30550, 30551, 30552, 25380, 25381, 24752, 24753, 24754, 19313, 19315, 19316, 19317,
 # 时空界皇 3463
 31250, 31251, 31252, 31253, 25734, 25735, 13533, 13532, 21881, 24687, 24688, 24689, 19190, 19191, 19192, 19193, 19194,
 # 蒂朵 4377
 35911, 35912, 35913, 35914, 35915, 35916, 24481, 27981, 27982, 27983,
 # 克罗 2977
 23122, 23123, 23124, 24603, 24604, 19034, 19035, 19036, 19037,
]

soulmarks = [360, 758, 909, 1825, 647]  # 克罗/草王 魂印（已知）；下面按需补

def sm(id):
    d = api(["get", "soulmark", str(id)])
    return d

out = io.open(OUT, "w", encoding="utf-8")
seen = set()
for sid in skills:
    if sid in seen: continue
    seen.add(sid)
    d = api(["get", "skill", str(sid)])
    if not d:
        out.write("SKILL %s NOTFOUND\n" % sid); continue
    eff = "; ".join(e.get("info") or "" for e in (d.get("skill_effect") or []))
    out.write("SKILL %s %s pow=%s pp=%s prio=%s hit=%s cat=%s type=%s | %s\n" % (
        sid, d.get("name"), d.get("power"), d.get("max_pp"), d.get("priority"),
        d.get("must_hit"), (d.get("category") or {}).get("id"), (d.get("type") or {}).get("id"), eff))
out.close()
print("done", len(seen))