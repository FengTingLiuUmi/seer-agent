import json
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider

p = SeerApiProvider()
rows = [json.loads(l) for l in open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\jybbrb_frames.jsonl", encoding="utf-8")]

# 找 S2C 里「像称号 id（150~607 区间）」出现多的命令
title_ids = set()
for t, _, _, _ in []:
    pass

print("=== 各 S2C 命令里 150..607 区间 id 的命中情况 ===")
for cmd in sorted({r['cmd'] for r in rows if r['dir'] == 's2c'}):
    hits = []
    for r in rows:
        if r['cmd'] == cmd and r['dir'] == 's2c':
            b = bytes.fromhex(r['bodyHex'])
            # 按 4 字节扫，找 150..607 的 u32
            for off in range(0, len(b) - 3, 4):
                v = struct.unpack_from('>I', b, off)[0]
                if 150 <= v <= 607:
                    hits.append(v)
    if hits:
        print(f"cmd={cmd} 命中 {len(set(hits))} 个不同 id，样例={sorted(set(hits))[:20]}")