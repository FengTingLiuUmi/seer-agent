import struct
import re

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
body = next(b for c, b in frames if c == 45963 and len(b) == 345)

# 完整 dump 前 96 字节（hex + 4字节 u32 注释）
print("45963 响应完整前 96 字节:")
for base in range(0, 96, 16):
    seg = body[base:base + 16]
    print(f"  {base:04x}: " + " ".join(f"{x:02x}" for x in seg))

# UTF-8 解码整段里的可读串
dec = body.decode("utf-8", "ignore")
print("\nUTF-8 可读串:", re.findall(r"[\u4e00-\u9fff]{2,}", dec))
print("完整 head:", body[:64].hex(" "))

# 找合法 species（1~6000）位置
from seer_rebuild.battle_data import BattleData
data = BattleData(r"F:\seer\seer_cfg\json")
print("\nspecies 候选（图鉴有名字）:")
for o in range(0, len(body) - 3, 4):
    v = struct.unpack_from(">I", body, o)[0]
    if v in data.species and 1 <= v <= 6000:
        print(f"  0x{o:04x} {v} {data.species[v].name}")

# 找 catch_time
print("\ncatch_time 候选:")
for o in range(0, len(body) - 3, 4):
    v = struct.unpack_from(">I", body, o)[0]
    if 0x54000000 <= v <= 0x6C000000:
        import datetime
        print(f"  0x{o:04x} {v} {datetime.datetime.fromtimestamp(v).strftime('%Y-%m-%d')}")