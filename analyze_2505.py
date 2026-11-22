import json, struct, sys

path = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\battle-records\timeline.jsonl"
rows = [json.loads(l) for l in open(path, encoding="utf-8")]
def u32(b, off):
    return struct.unpack_from(">I", b, off)[0] if len(b) >= off + 4 else None

EID = 0x6aff7845
for i, e in enumerate(rows):
    if e.get("cmd") != 2505:
        continue
    b = bytes.fromhex(e["body"])
    print(f"\n====== 2505 #{i} len={len(b)} ======")
    # 找敌方 eid 出现位置
    positions = []
    for off in range(0, len(b) - 3):
        if u32(b, off) == EID:
            positions.append(off)
    print("EID 位置:", positions)
    for p in positions:
        print(f"  eid@{p}: skill@-8={u32(b,p-8) if p>=8 else None} turn@-4={u32(b,p-4) if p>=4 else None} "
              f"cur@+24={u32(b,p+24)} max@+28={u32(b,p+28)}")
        print(f"     eid后16*4字节: " + " ".join(f"{u32(b,p+k)}" for k in range(0, 64, 4)))
    # 找 max=10000 的 [cur][max] 对
    pairs = []
    for off in range(0, len(b) - 7):
        mx = u32(b, off+4)
        if mx == 10000:
            cur = u32(b, off)
            pairs.append((off, cur))
    print("max=10000 的 [cur@off][max] 对:", pairs)
    # 找 max=10000 出现在 off 时其前 32 字节理解
    for off, cur in pairs[:6]:
        print(f"  off={off}: ... " + " ".join(f"{u32(b,off-16+k)}" for k in range(0, 40, 4)))