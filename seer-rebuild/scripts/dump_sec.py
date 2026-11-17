import json
import struct

for fn in ("seer-rebuild/pets_raw.jsonl", "seer-rebuild/pets_raw2.jsonl", "seer-rebuild/inventory_raw.jsonl"):
    try:
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
    except Exception as e:
        continue
    for r in rows:
        if r["cmd"] == 1001:
            body = bytes.fromhex(r["body"])
            print(f"== {fn} len={len(body)} ==")
            # 打印 0xcc0~0xd40 每 4 字节
            for off in range(0xCC0, 0xD40, 4):
                v = struct.unpack(">I", body[off:off+4])[0]
                print(f"  0x{off:04x}  {v:10d}  0x{v:08x}")
            break