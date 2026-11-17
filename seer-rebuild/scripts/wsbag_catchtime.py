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

# 找所有 catch_time（1.45e9 ~ 1.79e9 unix 时间戳），它们标记每只精灵
print("catch_time 候选（unix 时间戳）：")
for o in range(0, len(body) - 3, 4):
    v = struct.unpack_from(">I", body, o)[0]
    if 0x54000000 <= v <= 0x6B000000:  # 1.4e9 ~ 1.8e9
        print(f"  0x{o:04x}  {v}  ({__import__('datetime').datetime.fromtimestamp(v).strftime('%Y-%m-%d')})")
        # 往前找最近的合法 species
        for back in range(o - 4, max(0, o - 40), -4):
            s = struct.unpack_from(">I", body, back)[0]
            if s in data.species:
                print(f"        ↑ 前面 species = {s} {data.species[s].name} (0x{back:04x})")
                break