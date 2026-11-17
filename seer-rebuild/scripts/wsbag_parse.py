import struct

pcap = "seer-rebuild/wsbag.pcapng"
SERVER_PORT = 1211
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
                if sp == SERVER_PORT:
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    p = pd[ipoff + ihl + doff:]
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
count = struct.unpack_from(">I", body, 0)[0]
print("count =", count, "body len =", len(body))

from seer_rebuild.battle_data import BattleData

data = BattleData(r"F:\seer\seer_cfg\json")

# 找所有合法 species（图鉴里有名字的）位置
print("\n所有合法 species 位置:")
for o in range(0, len(body) - 3):
    v = struct.unpack_from(">I", body, o)[0]
    if v in data.species and 1 <= v <= 6000:
        print(f"  0x{o:04x}  {v}  {data.species[v].name}")

# 也搜 runtime id（0x5xxxxxxx~0x6xxxxxxx 这种）
print("\n可能的 runtime id（0x4xxxxxxx+）:")
for o in range(0, len(body) - 3, 4):
    v = struct.unpack_from(">I", body, o)[0]
    if 0x40000000 <= v <= 0x7FFFFFFF:
        print(f"  0x{o:04x}  {hex(v)}")