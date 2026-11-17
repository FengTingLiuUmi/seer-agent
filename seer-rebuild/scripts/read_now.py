"""直接登录，解析 1001 里全部装备/装扮 ID（含位置与上下文），不落盘。"""
import struct

from seer_rebuild.pets import run
from seer_rebuild.provider import SeerApiProvider

r = run("ACCOUNT", "PASSWORD", None)
body = None
for f in r["frames"]:
    if f["cmd"] == 1001:
        body = bytes.fromhex(f["body"])
        break

print("1001 len =", len(body))

# 找 0x130001~0x13FFFF 的 u32（按字节连续扫描，去重）
hits = []
for off in range(0, len(body) - 3):
    v = struct.unpack_from(">I", body, off)[0]
    if 0x130001 <= v <= 0x13FFFF:
        if not hits or (off - hits[-1][0]) > 3 or v != hits[-1][1]:
            hits.append((off, v))

print(f"0x13xxxx ID {len(hits)} 个：")
p = SeerApiProvider()
for off, v in hits:
    try:
        d = p.get("equip", v)
    except Exception:
        d = None
    name = d.get("name") if d else ""
    bonus = ""
    if d and d.get("bonus") and d["bonus"].get("desc"):
        bonus = d["bonus"]["desc"]
    print(f"  0x{off:04x}  {hex(v)}  {name}  {bonus}")