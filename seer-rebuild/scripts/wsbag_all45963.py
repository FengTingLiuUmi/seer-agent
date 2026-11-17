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


from seer_rebuild.battle_data import BattleData

data = BattleData(r"F:\seer\seer_cfg\json")

frames = scan_frames(b"".join(s2c))
bodies = [b for c, b in frames if c == 45963 and len(b) > 4]

# 对每个非空 45963，找：名字(UTF8) + species(>=4000 图鉴，避开小值误报) + catch
for idx, b in enumerate(bodies):
    names = re.findall(r"[\u4e00-\u9fff]{2,}", b.decode("utf-8", "ignore"))
    species = []
    for o in range(0, len(b) - 3, 4):
        v = struct.unpack_from(">I", b, o)[0]
        if v in data.species and v >= 4000:
            species.append((o, v, data.species[v].name))
    catch = []
    for o in range(0, len(b) - 3, 4):
        v = struct.unpack_from(">I", b, o)[0]
        if 0x54000000 <= v <= 0x6C000000:
            catch.append((o, v))
    print(f"[{idx}] 名字={names} species={species[:6]} catch={catch}")