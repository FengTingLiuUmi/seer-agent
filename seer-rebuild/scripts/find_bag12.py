"""重新定位「背包 12 只」：看 43706 响应与 1001 快照里是否有 12 只精灵。"""
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
            if pd[ipoff + 9] == 6:
                sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
                if sp == 1211 or dp == 1211:
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    payload = pd[ipoff + ihl + doff:]
                    if payload:
                        (s2c if sp == 1211 else c2s).append(payload)
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

# 找 43706 响应里所有合法 species（1~6000）
bodies = [b for c, b in frames if c == 43706]
print(f"43706 响应 {len(bodies)} 帧")
for b in bodies[:1]:
    print("len =", len(b))
    # 找合法 species id 的位置
    sps = []
    for o in range(0, len(b) - 3, 4):
        v = struct.unpack_from(">I", b, o)[0]
        if 1 <= v <= 6000:
            sps.append((o, v))
    print("合法 species 候选:", sps[:40])

# 关键：看 1001 快照里有没有 12 只（runtime id 列表）
b1001 = [b for c, b in frames if c == 1001]
print("\n1001 快照", len(b1001), "帧")
if b1001:
    b = b1001[0]
    print("1001 len =", len(b))
    # 找 12 个连续 runtime id（0x0xxxxxxx 或 0x6xxxxxxx 这种 32位）
    # 精灵 runtime id 之前见过 602211ae, 57c55a7f, 5ffd1dd6
    runtimes = []
    for o in range(0, len(b) - 3, 4):
        v = struct.unpack_from(">I", b, o)[0]
        # runtime id 是随机 32位，难区分；找 6xxxxxxx/5xxxxxxx 开头
        if 0x40000000 <= v <= 0x7FFFFFFF:
            runtimes.append((o, v))
    print("0x4xxxxxxx~0x7xxxxxxx 候选:", runtimes[:30])