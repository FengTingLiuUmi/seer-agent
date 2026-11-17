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
print("count=", count, "len=", len(body))

from seer_rebuild.battle_data import BattleData

data = BattleData(r"F:\seer\seer_cfg\json")

# 找每只精灵详情的起点：以「合法 species」且前有结构特征的位置为主
# 假设每只约 (len-4)/count 字节，dump 每块开头
per = (len(body) - 4) // count
print("每只约", per, "字节")
for k in range(count):
    base = 4 + k * per
    seg = body[base:base + 40]
    vals = [struct.unpack_from(">I", seg, o)[0] for o in range(0, 40, 4)]
    print(f"\n第{k+1}只 offset 0x{base:04x}: {[hex(v) for v in vals]}")
    # 找这块里的合法 species
    for o in range(0, per - 4, 4):
        v = struct.unpack_from(">I", body, base + o)[0]
        if v in data.species and 1 <= v <= 6000:
            print(f"    0x{base+o:04x} species={v} {data.species[v].name}")
            break