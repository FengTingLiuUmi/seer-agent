"""提取 wsbag 所有 45963 响应，decode UTF-8 找精灵名。"""
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
bodies = [(c, b) for c, b in frames if c == 45963]
print(f"45963 响应 {len(bodies)} 帧")

# decode UTF-8 子串
for idx, (c, b) in enumerate(bodies):
    if len(b) <= 4:
        continue
    # 提取 UTF-8 可读片段
    text = []
    for off in range(0, len(b)):
        # 尝试从每个位置 decode 连续的中文
        pass
    # 简单：找连续 CJK UTF-8
    import re
    dec = b.decode("utf-8", "ignore")
    names = re.findall(r"[\u4e00-\u9fff]{2,}", dec)
    print(f"[{idx}] len={len(b)} 名字片段: {names}")
    if idx >= 8:
        break