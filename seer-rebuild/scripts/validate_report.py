"""离线验证 battle_report 的血量解析（用 stage5_diag.txt 的 S2C 帧）。"""
import re
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.battle_report import (
    S2C_START, S2C_SKILL, _enemy_max_hp_from_frames, _enemy_hp_from_body,
    _team_max_hp_from_2504, _my_hp_from_body,
)


def load_frames(path):
    raw = open(path, 'rb').read()
    try:
        text = raw.decode('utf-16')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')
    frames = []
    for ln in text.splitlines():
        m = re.search(r'cmd=(\d+) result=(\S+) len=(\d+) body=([0-9a-f]+)', ln)
        if m:
            frames.append({"cmd": int(m.group(1)), "result": 0, "len": int(m.group(3)),
                           "body": m.group(4)})
    return frames


frames = load_frames(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\stage5_diag.txt")
print("总帧数:", len(frames), " 含2505:", sum(1 for f in frames if f['cmd'] == S2C_SKILL),
      " 含2504:", sum(1 for f in frames if f['cmd'] == S2C_START))

enemy_max = _enemy_max_hp_from_frames(frames)
print("敌方满血(发现):", enemy_max)

# 已知我方 catch（圣灵谱尼solo那场）
known = {0x57c55a7f, 0x62d8b735, 0x62ef6f18, 0x5ffd1dd6, 0x600b3f8c, 0x600b3f86}
for f in frames:
    if f['cmd'] == S2C_START:
        b = bytes.fromhex(f['body'])
        mm = _team_max_hp_from_2504(b, known)
        print("2504 我方 catch->满血:", {hex(k): v for k, v in mm.items()})
        break

print("逐 2505 敌方当前血:")
n = 0
for f in frames:
    if f['cmd'] != S2C_SKILL:
        continue
    b = bytes.fromhex(f['body'])
    h = _enemy_hp_from_body(b, enemy_max)
    print(f"  2505 len={len(b)} 敌当前血={h}")
    n += 1
    if n >= 12:
        break

# 测试我方血：圣灵谱尼在 2505 里
for f in frames:
    if f['cmd'] == S2C_SKILL and 0x57c55a7f in [0]:
        pass