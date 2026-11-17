import struct
from collections import Counter

pcap = "seer-rebuild/petbag_ws.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
pairs = Counter()
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
            proto = pd[ipoff + 9]
            sip = pd[ipoff + 12:ipoff + 16]
            dip = pd[ipoff + 16:ipoff + 20]
            if proto == 6:
                sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
                pairs[(sip, sp, dip, dp)] += 1
                break
    i += bl

def ip(b):
    return ".".join(str(x) for x in b)

print("所有 TCP 会话 (src:port -> dst:port) [非443/80]:")
for (sip, sp, dip, dp), v in sorted(pairs.items(), key=lambda x: -x[1]):
    if dp not in (443, 80) and sp not in (443, 80, 53):
        print(f"  {ip(sip)}:{sp} -> {ip(dip)}:{dp}   x{v}")