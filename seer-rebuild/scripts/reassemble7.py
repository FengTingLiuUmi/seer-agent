import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
s2c = []
c2s = []
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
            proto = pd[ipoff + 9]
            if proto == 6:
                sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
                if sp == 1211 or dp == 1211:
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    payload = pd[ipoff + ihl + doff:]
                    if payload:
                        (s2c if sp == 1211 else c2s).append(payload)
                break
    i += bl

s2c_buf = b"".join(s2c)
c2s_buf = b"".join(c2s)
print("C2S", len(c2s_buf), "S2C", len(s2c_buf))


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
        frames.append((cmd, total - 17, buf[off + 17:off + total]))
        off += total
    return frames


from collections import Counter

s2c_frames = scan_frames(s2c_buf)
c2s_frames = scan_frames(c2s_buf)
print(f"\nS2C {len(s2c_frames)} 帧, cmd分布:")
c = Counter(f[0] for f in s2c_frames)
for cmd, cnt in c.most_common(40):
    print(f"  cmd={cmd} x{cnt}")

# 大 body 样本
print("\nS2C 大 body 样本:")
shown = set()
for cmd, blen, body in s2c_frames:
    if blen > 80 and cmd not in shown:
        shown.add(cmd)
        print(f"  cmd={cmd} len={blen} body={body[:140].hex()}")