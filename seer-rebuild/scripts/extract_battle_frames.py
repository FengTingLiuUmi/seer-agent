"""从 cmdlog4.jsonl 提取 2503/2504/2505/2506/2595/2394/2441 战斗帧 body，去重打印。"""
import json
from pathlib import Path

P = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\cmdlog4.jsonl")
CMDS = {2503, 2504, 2505, 2506, 2595, 2394, 2441, 2404, 2405, 2408}

seen = {}
for line in P.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    direction = "C2S" if line.startswith("SEERWS ") else "S2C"
    # 去掉 "SEERWS " / "SEERWSR " 前缀
    if line.startswith("SEERWSR "):
        line = line[len("SEERWSR "):]
    elif line.startswith("SEERWS "):
        line = line[len("SEERWS "):]
    try:
        j = json.loads(line)
    except json.JSONDecodeError:
        continue
    cmd = j.get("cmd")
    if cmd not in CMDS:
        continue
    body = j.get("bodyHex", "")
    key = (cmd, body)
    if key in seen:
        continue
    seen[key] = True
    print(f"{direction} cmd={cmd} len={len(body)//2} body={body}")