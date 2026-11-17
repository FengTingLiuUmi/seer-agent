"""解析 petbag2 抓包：找游戏端口，双向扫描 C2S/S2C 帧（含放回仓库、加入背包命令）。"""
import struct
from collections import Counter

pcap = "seer-rebuild/petbag2.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0

# 1) 找游戏端口（非 443/80/53 的 TCP，且包多）
ports = Counter()
ips = Counter()
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
            if pd[ipoff + 9] != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            ports[(sp, dp)] += 1
            ips[(pd[ipoff + 16:ipoff + 20])] += 1
            break
    i += bl

print("端口分布 top20:")
for k, v in ports.most_common(20):
    print("  ", k, v)
print("远端 IP top10:")
for k, v in ips.most_common(10):
    print("  ", ".".join(str(x) for x in k), v)