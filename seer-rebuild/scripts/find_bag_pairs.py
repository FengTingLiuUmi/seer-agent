import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
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
                if sp == 1211:
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    payload = pd[ipoff + ihl + doff:]
                    if payload:
                        s2c.append(payload)
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
body = next(b for c, b in frames if c == 1001)

from seer_rebuild.battle_data import BattleData
data = BattleData(r"F:\seer\seer_cfg\json")

# 找 [species(1..6000 且在图鉴)][runtime(0x40000000~0x7fffffff)] 相邻对
pairs = []
for o in range(0, len(body) - 8, 4):
    a = struct.unpack_from(">I", body, o)[0]
    b = struct.unpack_from(">I", body, o + 4)[0]
    if a in data.species and 0x20000000 <= b <= 0x7FFFFFFF:
        pairs.append((o, a, data.species[a].name, hex(b)))

print("species+runtime 相邻对：")
for o, sid, name, rt in pairs[:40]:
    print(f"  0x{o:04x}  {sid:6d} {name:12s}  runtime={rt}")

# 反过来 [runtime][species]
pairs2 = []
for o in range(0, len(body) - 8, 4):
    a = struct.unpack_from(">I", body, o)[0]
    b = struct.unpack_from(">I", body, o + 4)[0]
    if b in data.species and 0x20000000 <= a <= 0x7FFFFFFF:
        pairs2.append((o, hex(a), b, data.species[b].name))

print("\nruntime+species 相邻对：")
for o, rt, sid, name in pairs2[:40]:
    print(f"  0x{o:04x}  runtime={rt}  {sid:6d} {name}")