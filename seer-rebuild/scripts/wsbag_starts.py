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
count = struct.unpack_from(">I", body, 0)[0]

from seer_rebuild.battle_data import BattleData

data = BattleData(r"F:\seer\seer_cfg\json")

# 找 [species][0][0][0] 模式（精灵块开头）
print(f"count={count}, 找 [species][0][0][0] 块开头:")
starts = []
for o in range(0, len(body) - 16, 4):
    s = struct.unpack_from(">I", body, o)[0]
    if s in data.species and 1 <= s <= 6000:
        z1 = struct.unpack_from(">I", body, o + 4)[0]
        z2 = struct.unpack_from(">I", body, o + 8)[0]
        z3 = struct.unpack_from(">I", body, o + 12)[0]
        if z1 == 0 and z2 == 0 and z3 == 0:
            starts.append((o, s, data.species[s].name))
            print(f"  0x{o:04x}  {s:6d} {data.species[s].name}")

print(f"\n共 {len(starts)} 个块开头（期望 {count} 只）")