import json
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
rows = [json.loads(l) for l in open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\jybbrb_frames.jsonl", encoding="utf-8")]

# 取 2003 S2C（登录快照）里的 title id
ids = set()
for r in rows:
    if r['cmd'] == 2003 and r['dir'] == 's2c':
        b = bytes.fromhex(r['bodyHex'])
        for off in range(0, len(b) - 3):
            v = struct.unpack_from('>I', b, off)[0]
            if 150 <= v <= 607:
                ids.add(v)

names = {}
for tid in sorted(ids):
    try:
        d = p.get("title", tid)
    except Exception:
        continue
    if not d:
        continue
    if d.get("is_ability_bonus"):
        names[tid] = (d.get("name"), d.get("ability_desc"))

print(f"账号 2003 快照里出现的称号 id 共 {len(ids)} 个，其中能力加成(属性称号) {len([k for k,v in names.items() if v[1]!='(非能力加成)'])} 个：")
for tid in sorted(names):
    nm, desc = names[tid]
    print(f"  {tid}  {nm}  [{desc}]")