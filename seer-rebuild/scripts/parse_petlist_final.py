"""从抓包解析 2361 精灵列表 → species_id → 中文名。"""
import struct

from seer_rebuild.battle_data import BattleData

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
body = None
for cmd, b in frames:
    if cmd == 2361:
        body = b
        break

assert body is not None, "没找到 2361"
count = struct.unpack_from(">I", body, 0)[0]
pets = []
for k in range(count):
    off = 4 + k * 12
    if off + 12 > len(body):
        break
    species = struct.unpack_from(">I", body, off)[0]
    flag = struct.unpack_from(">I", body, off + 4)[0]
    catch = struct.unpack_from(">I", body, off + 8)[0]
    pets.append((species, flag, catch))

print(f"精灵总数（2361 列表）: {len(pets)}")

data = BattleData(r"F:\seer\seer_cfg\json")
print("\n全部精灵:")
for species, flag, catch in pets:
    sp = data.species.get(species)
    name = sp.name if sp else f"?{species}"
    mark = " ⭐首发" if flag == 1 else ""
    print(f"  {species:6d}  {name}{mark}")