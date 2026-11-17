"""在 1001 快照里找精灵 runtime id，定位精灵背包段。"""
import json

for fn in ("seer-rebuild/pets_raw2.jsonl", "seer-rebuild/pets_raw.jsonl", "seer-rebuild/inventory_raw.jsonl"):
    try:
        rows = [json.loads(l) for l in open(fn, encoding="utf-8")]
    except Exception:
        continue
    for r in rows:
        if r["cmd"] != 1001:
            continue
        body = bytes.fromhex(r["body"])
        print(f"== {fn} len={len(body)} ==")
        # 已知精灵 runtime id（feature1/feature2 抓包里 2301/2304 用过）
        for marker in (bytes.fromhex("6ace3260"), bytes.fromhex("602211ae"), bytes.fromhex("6ad1d34f")):
            idx = body.find(marker)
            if idx >= 0:
                print(f"  找到 runtime id {marker.hex()} @ 0x{idx:04x}")
                print("    上下文:", body[max(0,idx-16):idx+64].hex(" "))
        break