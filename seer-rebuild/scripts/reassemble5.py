import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
s2c_buf = bytearray()
c2s_buf = bytearray()
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
            if sp != 1211 and dp != 1211:
                break
            doff = (pd[ipoff + ihl + 12] >> 4) * 4
            payload = pd[ipoff + ihl + doff:]
            if payload:
                (s2c_buf if sp == 1211 else c2s_buf).extend(payload)
            break
    i += bl

print("C2S 流", len(c2s_buf), "S2C 流", len(s2c_buf))

from seer_rebuild.protocol import FrameSplitter, parse_h5

# 因为按文件顺序可能混入重传，用逐帧扫描（容错）而非严格 splitter
def scan_frames(buf, label):
    frames = []
    off = 0
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]
        ver = buf[off + 4]
        if total < 17 or total > 0x800000 or ver not in (0x31, 0x3E):
            off += 1
            continue
        if off + total > len(buf):
            off += 1
            continue
        cmd = struct.unpack_from(">I", buf, off + 5)[0]
        res = struct.unpack_from(">i", buf, off + 13)[0]
        frames.append((cmd, res, total - 17, buf[off + 17:off + total]))
        off += total
    return frames

for label, buf in (("C2S", c2s_buf), ("S2C", s2c_buf)):
    frames = scan_frames(bytes(buf), label)
    print(f"\n=== {label} ({len(frames)} 帧) ===")
    from collections import Counter
    c = Counter(f[0] for f in frames)
    print("  cmd 分布:", dict(c.most_common(20)))
    for cmd, res, blen, body in frames[:15]:
        if cmd not in (8002, 3452, 45827, 4395, 2002):
            print(f"    cmd={cmd} len={blen} body={body[:100].hex()}")