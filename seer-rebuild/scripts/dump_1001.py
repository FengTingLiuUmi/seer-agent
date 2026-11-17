"""实时登录，完整 dump 1001 body 并找出所有 0x13xxxx 装备/装扮 ID。"""
import json
import struct

from seer_rebuild.pets import run

r = run("ACCOUNT", "PASSWORD", None)
for f in r["frames"]:
    if f["cmd"] == 1001:
        body = bytes.fromhex(f["body"])
        open("seer-rebuild/live_1001.bin", "wb").write(body)
        print("1001 len", len(body))

        # 找所有 0x130000~0x13FFFF 的单次出现的 u32（按 4 字节对齐）
        hits = []
        i = 0
        for off in range(0, len(body) - 3):
            v = struct.unpack_from(">I", body, off)[0]
            if 0x130000 <= v <= 0x13FFFF:
                hits.append((off, v))
        # 去重相邻
        seen = []
        for off, v in hits:
            if not seen or v != seen[-1][1]:
                seen.append((off, v))
        print(f"0x13xxxx IDs: {len(seen)}")
        for off, v in seen:
            print(f"  0x{off:04x}  {hex(v)}  {v}")
        break