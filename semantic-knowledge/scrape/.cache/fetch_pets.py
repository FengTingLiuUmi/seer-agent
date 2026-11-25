import json, subprocess, sys, io, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "petsk.json")
SK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skillsk.json")

def api(args):
    p = subprocess.run(["seerapi"] + args, capture_output=True)
    b = p.stdout
    for enc in ("utf-8", "gbk"):
        try:
            return json.loads(b.decode(enc))
        except Exception:
            continue
    return None

pet_ids = [3613, 3322, 5000, 3437, 3844, 3573, 3329, 3463, 4377, 2977]
pets = {}
skill_ids = set()
for pid in pet_ids:
    d = api(["get", "pet", str(pid)])
    if not d:
        continue
    pets[pid] = {"name": d.get("name"), "type": d.get("type"), "skills": [], "soulmark": d.get("soulmark")}
    for s in d.get("skill") or []:
        sid = s["skill"]["id"]
        pets[pid]["skills"].append({"id": sid, "lv": s.get("learning_level"), "fifth": s.get("is_fifth"), "special": s.get("is_special"), "adv": s.get("is_advanced")})
        skill_ids.add(sid)

skills = {}
for sid in sorted(skill_ids):
    d = api(["get", "skill", str(sid)])
    if not d:
        continue
    skills[sid] = {
        "name": d.get("name"), "power": d.get("power"), "pp": d.get("max_pp"),
        "acc": d.get("accuracy"), "prio": d.get("priority"), "must_hit": d.get("must_hit"),
        "cat": (d.get("category") or {}).get("id"), "type": (d.get("type") or {}).get("id"),
        "eff": [e.get("info") for e in (d.get("skill_effect") or [])],
        "hide": d.get("hide_effect"),
    }

with io.open(OUT, "w", encoding="utf-8") as f:
    json.dump(pets, f, ensure_ascii=False, indent=1)
with io.open(SK, "w", encoding="utf-8") as f:
    json.dump(skills, f, ensure_ascii=False, indent=1)

print("pets", len(pets), "skills", len(skills))