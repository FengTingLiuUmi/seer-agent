"""找账号精英仓库(2361)里对 神秘+战斗 有克制的精灵（超能/虚空/虫/飞行）。"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
TARGET = {4: "飞行", 10: "超能", 21: "虫", 26: "虚空"}

rows = [json.loads(l) for l in open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\jybbrb_frames.jsonl", encoding="utf-8")]
elite = []
for r in rows:
    if r["cmd"] == 2361 and r["dir"] == "s2c":
        b = bytes.fromhex(r["bodyHex"])
        c = struct.unpack_from(">I", b, 0)[0]
        for i in range(c):
            o = 4 + i * 12
            if o + 12 > len(b):
                break
            s, f, ct = struct.unpack_from(">III", b, o)
            if 1 <= s <= 6000:
                elite.append((s, f, ct))
        break

print("精英仓库条数:", len(elite))
seen = {}
for s, f, ct in elite:
    d = p.get("pet", s, fields=["id", "name", "type"])
    if not d:
        continue
    tid = (d.get("type") or {}).get("id")
    comb = p.get("element_type_combination", tid) if tid else None
    if not comb:
        continue
    prim = (comb.get("primary") or {}).get("id")
    sec = (comb.get("secondary") or {}).get("id")
    hits = [TARGET[x] for x in (prim, sec) if x in TARGET]
    if hits:
        key = s
        if key not in seen:
            seen[key] = {"name": d.get("name"), "type": comb.get("name"), "cats": set(hits), "catches": []}
        seen[key]["catches"].append(ct)

for s in sorted(seen):
    info = seen[s]
    print(f"{s} {info['name']}  [{info['type']}]  克={sorted(info['cats'])}  catch={[hex(c) for c in info['catches']]}")