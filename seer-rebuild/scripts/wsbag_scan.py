import struct

pcap = "seer-rebuild/wsbag.pcapng"
SERVER_PORT = 1211
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
            if pd[ipoff + 9] == 6:
                sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
                if sp == SERVER_PORT or dp == SERVER_PORT:
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    payload = pd[ipoff + ihl + doff:]
                    if payload:
                        (s2c if sp == SERVER_PORT else c2s).append(payload)
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


from collections import Counter

c2s_frames = scan_frames(b"".join(c2s))
s2c_frames = scan_frames(b"".join(s2c))
print("C2S", len(c2s_frames), "帧:", dict(Counter(c for c, _ in c2s_frames).most_common(20)))
print("S2C", len(s2c_frames), "帧:", dict(Counter(c for c, _ in s2c_frames).most_common(20)))

# dump S2C 里与精灵相关的 cmd body
for cmd_want in (2361, 43706, 2301, 2303, 2003):
    bodies = [b for c, b in s2c_frames if c == cmd_want]
    print(f"\n--- S2C cmd={cmd_want} ({len(bodies)}) ---")
    for b in bodies[:2]:
        print(f"  len={len(b)} 前80字节: {b[:80].hex(' ')}")