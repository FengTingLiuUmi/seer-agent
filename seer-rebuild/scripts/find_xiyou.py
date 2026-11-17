import json
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.battle_data import BattleData

d = BattleData(r"F:\seer\seer_cfg\json")

rows = [json.loads(l) for l in open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\jybbrb_frames.jsonl", encoding="utf-8")]
species = {}
for r in rows:
    if r["cmd"] == 2361 and r["dir"] == "s2c":
        b = bytes.fromhex(r["bodyHex"])
        c = struct.unpack_from(">I", b, 0)[0]
        for i in range(c):
            o = 4 + i * 12
            if o + 12 > len(b):
                break
            s = struct.unpack_from(">I", b, o)[0]
            f = struct.unpack_from(">I", b, o + 4)[0]
            ct = struct.unpack_from(">I", b, o + 8)[0]
            if 1 <= s <= 6000:
                species.setdefault(s, []).append((f, ct))
        break

print("总species数:", len(species))
kw = ["三藏", "蒙奇", "天河", "悟净", "沙", "悟空", "美猴", "唐僧", "八戒", "博迪", "金蝉", "齐天", "大圣", "白龙", "西游", "猴"]
for s in sorted(species):
    nm = d.species.get(s).name if d.species.get(s) else ""
    if any(k in nm for k in kw):
        print(f"{s}  {nm}  catch={[hex(ct) for _, ct in species[s]]}")