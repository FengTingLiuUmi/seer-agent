"""按 TCP seq 重组 1211 连接双向流，解析精灵列表（S2C）。"""
import struct
from collections import defaultdict

pcap = "seer-rebuild/petbag_ws.pcapng"
SERVER_PORT = 1211

d = open(pcap, "rb").read()
endian = "<"
i = 0
# 每个方向收集 (seq, payload)
streams = {"C2S": [], "S2C": []}
while i + 8 <= len(d):
    bt, bl = struct.unpack_from(endian + "II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from(endian + "I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        for ipoff in range(0, min(len(pd) - 40, 64)):
            if len(pd) < ipoff + 40:
                break
            if pd[ipoff] >> 4 != 4:
                continue
            ihl = (pd[ipoff] & 15) * 4
            if pd[ipoff + 9] != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            if sp != SERVER_PORT and dp != SERVER_PORT:
                break
            seq = struct.unpack_from(">I", pd, ipoff + ihl + 4)[0]
            doff = (pd[ipoff + ihl + 12] >> 4) * 4
            payload = pd[ipoff + ihl + doff:]
            direction = "S2C" if sp == SERVER_PORT else "C2S"
            if payload:
                streams[direction].append((seq, payload))
            break
    i += bl

from seer_rebuild.protocol import FrameSplitter

for direction in ("C2S", "S2C"):
    packs = sorted(streams[direction], key=lambda x: x[0])
    # 去重重传（同 seq）
    buf = bytearray()
    last_seq = None
    for seq, payload in packs:
        if seq == last_seq:
            continue
        last_seq = seq
        buf.extend(payload)
    sp = FrameSplitter("h5")
    try:
        frames = sp.push(bytes(buf))
    except Exception as e:
        print(f"{direction} 流解析失败: {e}, 流长 {len(buf)}")
        continue
    print(f"\n=== {direction} ({len(frames)} 帧, 流 {len(buf)} B) ===")
    seen = {}
    for f in frames:
        seen.setdefault(f.cmd, [0, None])
        seen[f.cmd][0] += 1
        if seen[f.cmd][1] is None and f.cmd not in (3452, 45827, 8002):
            seen[f.cmd][1] = f.body.hex()
    for cmd, (cnt, body) in sorted(seen.items()):
        print(f"  cmd={cmd} x{cnt}")
        if body:
            print(f"       body={body[:160]}")