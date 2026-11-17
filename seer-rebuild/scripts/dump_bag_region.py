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
print("1001 len", len(body))

# 找已知 runtime id（时空界神 3463 / 圣灵谱尼 5000 的 runtime 未知，但 602211ae 是见过的）
# dump 0x820~0xa00 每 4 字节，找连续 12 个"大随机数"（runtime id）
for base in range(0x800, 0xB00, 0x40):
    vals = [struct.unpack_from(">I", body, base + k * 4)[0] for k in range(16)]
    print(f"0x{base:04x}: " + " ".join(f"{v:08x}" for v in vals))