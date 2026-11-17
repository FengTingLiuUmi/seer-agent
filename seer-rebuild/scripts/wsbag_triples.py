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

from seer_rebuild.battle_data import BattleData

data = BattleData(r"F:\seer\seer_cfg\json")

# 找 [species][flag(0/1)][catch_time] 三元组
print("背包精灵（[species, flag, catch] 三元组）：")
found = []
for o in range(0, len(body) - 12):
    s = struct.unpack_from(">I", body, o)[0]
    f = struct.unpack_from(">I", body, o + 4)[0]
    c = struct.unpack_from(">I", body, o + 8)[0]
    if s in data.species and f in (0, 1) and 0x50000000 <= c <= 0x6C000000:
        name = data.species[s].name
        if (s, f, c) not in found:
            found.append((s, f, c))
            print(f"  0x{o:04x}  species={s:6d} {name:14s} flag={f} catch={c}")