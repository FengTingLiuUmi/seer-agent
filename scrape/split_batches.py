# -*- coding: utf-8 -*-
"""把 threads-content.jsonl 切成每 20 帖一批，供多 agent 并行抽取。
同时产出 manifest.json；并保证 factor-extract 输出目录存在。"""
import os, json, math

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SRC = f"{HERE}/threads-content.jsonl"
OUTD = f"{HERE}/batches"
EXTD = f"{HERE}/factor-extract"
os.makedirs(OUTD, exist_ok=True)
os.makedirs(EXTD, exist_ok=True)

lines = [l for l in open(SRC, encoding="utf-8") if l.strip()]
BS = 20
nb = math.ceil(len(lines) / BS)
manifest = []
for i in range(nb):
    sid = f"{i + 1:02d}"
    chunk = lines[i * BS:(i + 1) * BS]
    fp = f"{OUTD}/threads-batch-{sid}.jsonl"
    with open(fp, "w", encoding="utf-8") as f:
        f.write("".join(chunk))
    manifest.append({"id": sid, "file": fp, "count": len(chunk)})

with open(f"{OUTD}/manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

print(f"total_threads={len(lines)} nbatches={nb}")
for m in manifest:
    print(f"  batch-{m['id']}: {m['count']} 帖")