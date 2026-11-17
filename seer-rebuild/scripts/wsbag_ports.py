"""解析 wsbag：找游戏端口，双向重组，解析 S2C 精灵段。"""
import struct

pcap = "seer-rebuild/wsbag.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
ports = {}
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
                ports[(sp, dp)] = ports.get((sp, dp), 0) + 1
                break
    i += bl
print("端口分布:", dict(sorted(ports.items(), key=lambda x: -x[1])))