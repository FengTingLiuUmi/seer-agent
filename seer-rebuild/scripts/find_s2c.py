import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
n = 0
while i + 8 <= len(d) and n < 5:
    bt, bl = struct.unpack_from(endian + "II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from(endian + "I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        # 直接在整个 pd 里搜 TCP 端口 1211（源）的字节模式 04bb = 1211
        # 更简单：找 any ipoff where ipv4 and ports contain 1211 as src
        for ipoff in range(0, min(len(pd) - 40, 96)):
            if len(pd) < ipoff + 40:
                break
            if pd[ipoff] >> 4 != 4:
                continue
            ihl = (pd[ipoff] & 0x0F) * 4
            if pd[ipoff + 9] != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            if sp == 1211:
                doff = (pd[ipoff + ihl + 12] >> 4) * 4
                payload = pd[ipoff + ihl + doff:]
                print(f"找到 S2C 包: ipoff={ipoff} ihl={ihl} doff={doff} payload_len={len(payload)}")
                print("  payload 前 80:", payload[:80].hex(" "))
                n += 1
                break
            if dp == 1211 or sp == 1211:
                break
    i += bl
print("done, n =", n)