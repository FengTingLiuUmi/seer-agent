"""实时登录并发宠物命令，dump 全部帧 + 找精灵 ID。"""
import struct

from seer_rebuild.pets import run

r = run("ACCOUNT", "PASSWORD", None)
print("收到帧总数:", len(r["frames"]))
for f in r["frames"]:
    print(f"  cmd={f['cmd']} result={f['result']} len={f['len']} body={f['body'][:40]}")

# 1001 快照里找精灵 ID（species 1~6000 或 pet 相关）
for f in r["frames"]:
    if f["cmd"] == 1001:
        body = bytes.fromhex(f["body"])
        # 找连续的小整数（精灵 id / catchTime 对），只列 1~6000 的 u32
        cand = []
        for off in range(0, len(body) - 3, 4):
            v = struct.unpack(">I", body[off:off + 4])[0]
            if 1 <= v <= 6000:
                cand.append((off, v))
        print("1001 里 1~6000 的 u32 个数:", len(cand), "前 20:")
        for off, v in cand[:20]:
            print(f"    0x{off:04x}  {v}")