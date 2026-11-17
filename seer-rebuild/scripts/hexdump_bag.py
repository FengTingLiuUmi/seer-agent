import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
s2c = []
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
            if pd[ipoff + 9] == 6:
                sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
                if sp == 1211:
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    payload = pd[ipoff + ihl + doff:]
                    if payload:
                        s2c.append(payload)
                break
    i += bl


def scan_frames(buf):
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
        frames.append((cmd, buf[off + 17:off + total]))
        off += total
    return frames


frames = scan_frames(b"".join(s2c))
body = next(b for c, b in frames if c == 1001)

# 从 0x840 开始，原始字节 hex dump（每行 16 字节）
print("1001 快照 0x840~0x900 原始字节:")
for base in range(0x840, 0x900, 16):
    seg = body[base:base + 16]
    print(f"  {base:04x}: " + " ".join(f"{x:02x}" for x in seg))