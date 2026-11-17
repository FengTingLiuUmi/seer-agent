"""按时间顺序还原 wsbag 完整双向交互，定位 session key 握手。"""
import struct

pcap = "seer-rebuild/wsbag.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
endian = "<"
i = 0
# 收集 (方向, payload) 按文件顺序
events = []
while i + 8 <= len(d):
    bt, bl = struct.unpack_from(endian + "II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from(endian + "I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        for o in range(0, min(len(pd) - 40, 64)):
            if len(pd) < o + 40:
                break
            if pd[o] >> 4 != 4:
                continue
            ihl = (pd[o] & 15) * 4
            if pd[o + 9] == 6:
                sp, dp = struct.unpack_from(">HH", pd, o + ihl)
                if sp == SERVER_PORT or dp == SERVER_PORT:
                    doff = (pd[o + ihl + 12] >> 4) * 4
                    p = pd[o + ihl + doff:]
                    if p:
                        direction = "S2C" if sp == SERVER_PORT else "C2S"
                        events.append((direction, p))
                break
    i += bl


# 逐包内嵌扫描帧（因为粘包/分片，用容错扫描 + 顺序）
def iter_frames(payloads):
    for direction, p in payloads:
        # 内嵌扫描完整帧
        off = 0
        while off + 17 <= len(p):
            total = struct.unpack_from(">I", p, off)[0]
            ver = p[off + 4]
            if total < 17 or total > 0x800000 or ver not in (0x31, 0x3E):
                off += 1
                continue
            if off + total > len(p):
                break
            cmd = struct.unpack_from(">I", p, off + 5)[0]
            body = p[off + 17:off + total]
            yield direction, cmd, body
            off += total


print("登录后前 40 个交互（按时间序）：")
n = 0
for direction, cmd, body in iter_frames(events):
    if n >= 40:
        break
    n += 1
    tag = ""
    if cmd in (45963, 41228, 46046, 43706, 2304, 1016, 1001):
        tag = "  ★"
    print(f"{direction} cmd={cmd:6d} len={len(body):4d}{tag}  body前24={body[:24].hex()}")