import json, subprocess, os, io

BASE = os.path.dirname(os.path.abspath(__file__))
idx = json.load(io.open(os.path.join(BASE, "..", "skills-index.json"), encoding="utf-8"))
name_by_id = {s["id"]: s["name"] for s in idx}

def api(args):
    p = subprocess.run(["seerapi"] + args, capture_output=True)
    for enc in ("utf-8", "gbk"):
        try:
            return json.loads(p.stdout.decode(enc))
        except Exception:
            continue
    return None

pet_ids = [3613, 3322, 5000, 3437, 3844, 3573, 3329, 3463, 4377, 2977]
out = io.open(os.path.join(BASE, "skill_names.txt"), "w", encoding="utf-8")
for pid in pet_ids:
    d = api(["get", "pet", str(pid)])
    if not d:
        continue
    out.write("== %s %s ==\n" % (pid, d.get("name")))
    for s in d.get("skill") or []:
        sid = s["skill"]["id"]
        nm = name_by_id.get(sid, "?")
        tag = []
        if s.get("is_fifth"): tag.append("FIFTH")
        if s.get("is_special"): tag.append("SP")
        if s.get("is_advanced"): tag.append("ADV")
        out.write("  %s | %s | %s\n" % (sid, nm, ",".join(tag)))
    out.write("\n")
out.close()
print("done")