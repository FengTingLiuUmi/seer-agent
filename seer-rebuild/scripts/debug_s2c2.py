import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
endian = "<"
i = 0
s2c_payloads = 0
s2c_total = 0
total_payload_bytes = 0
first_payloads = []
while i + 8 <= len(d):
    bt, bl = struct.unpack_from(endian + "II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from(endian + "I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        for ipoff in range(0, min(len(pd) - 40, 96)):
            if len(pd) < ipoff + 40:
                break
            if pd[ipoff] >> 4 != 4:
                continue
            ihl = (pd[ipoff] & 15) * 4
            if pd[ipoff + 9] != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            if sp != SERVER_PORT and dp != SERVER_PORT:
                break
            if sp == SERVER_PORT:
                s2c_total += 1
                doff = (pd[ipoff + ihl + 12] >> 4) * 4
                payload = pd[ipoff + ihl + doff:]
                if payload:
                    s2c_payloads += 1
                    total_payload_bytes += len(payload)
                    if len(first_payloads) < 5:
                        first_payloads.append((len(payload), payload[:40].hex(" ")))
            break
    i += bl

print(f"S2C 包总数={s2c_total}  有 payload 的={s2c_payloads}  总 payload 字节={total_payload_bytes}")
for plen, h in first_payloads:
    print(f"  len={plen} {h}")