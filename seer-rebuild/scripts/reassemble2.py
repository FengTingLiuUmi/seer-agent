import struct
from collections import defaultdict

pcap = "seer-rebuild/petbag_ws.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
endian = "<"

streams = {"C2S": [], "S2C": []}
i = 0
while i + 8 <= len(d):
    bt, bl = struct.unpack_from(endian + "II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from(endian + "I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        found = False
        for ipoff in range(0, min(len(pd) - 40, 96)):
            if len(pd) < ipoff + 40:
                break
            if pd[ipoff] >> 4 != 4:
                continue
            ihl = (pd[ipoff] & 0x0F) * 4
            sip = pd[ipoff + 12:ipoff + 16]
            dip = pd[ipoff + 16:ipoff + 20]
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
            found = True
            break
        if not found:
            i += bl
            continue
    i += bl

from seer_rebuild.protocol import FrameSplitter

for direction in ("C2S", "S2C"):
    packs = sorted(streams[direction], key=lambda x: x[0])
    buf = bytearray()
    seen_seq = set()
    for seq, payload in packs:
        if seq in seen_seq:
            continue
        seen_seq.add(seq)
        buf.extend(payload)
    sp = FrameSplitter("h5")
    try:
        frames = sp.push(bytes(buf))
    except Exception as e:
        print(f"{direction} 解析失败: {e}, 流长 {len(buf)} B, 包数 {len(packs)}")
        continue
    print(f"\n=== {direction} ({len(frames)} 帧, 流 {len(buf)} B, 包 {len(packs)}) ===")
    seen = {}
    for f in frames:
        seen.setdefault(f.cmd, [0, None])
        seen[f.cmd][0] += 1
        if seen[f.cmd][1] is None and f.cmd not in (8002,):
            seen[f.cmd][1] = f.body.hex()
    for cmd, (cnt, body) in sorted(seen.items()):
        print(f"  cmd={cmd} x{cnt}")
        if body and len(body) > 8:
            print(f"       body={body[:160]}")