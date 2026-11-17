import struct

pcap = "seer-rebuild/wsbag.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
i = 0
s2c = []
while i + 8 <= len(d):
    bt, bl = struct.unpack_from("<II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from("<I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        for o in range(0, min(len(pd) - 40, 64)):
            if len(pd) < o + 40:
                break
            if pd[o] >> 4 != 4:
                continue
            ihl = (pd[o] & 15) * 4
            if pd[o + 9] == 6:
                sp, dp = struct.unpack_from(">HH", pd, o + ihl)
                if sp == SERVER_PORT:
                    doff = (pd[o + ihl + 12] >> 4) * 4
                    p = pd[o + ihl + doff:]
                    if p:
                        s2c.append(p)
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
body = next(b for c, b in frames if c == 43706)

# 找已知主力精灵 species 的位置
known = {3022: "王之哈莫", 5000: "圣灵谱尼", 3512: "帝皇之御", 3463: "时空界皇",
         3437: "艾欧丽娅", 3329: "六界帝神", 3045: "六界神王", 3519: "沙悟净",
         3409: "三藏", 2727: "蒙奇多克", 2735: "天河神将", 3291: "瀚宇星皇"}
for o in range(0, len(body) - 3):
    v = struct.unpack_from(">I", body, o)[0]
    if v in known and (o % 4 == 0):
        print(f"0x{o:04x}  {v}  {known[v]}")

print("\ncount 后的前 8 个 u32（第一只开头）:")
for o in range(0, 32, 4):
    v = struct.unpack_from(">I", body, o)[0]
    print(f"  [0x{o:02x}] {v}")