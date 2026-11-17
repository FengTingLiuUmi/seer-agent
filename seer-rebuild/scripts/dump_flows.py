"""Dump 119.249.103.49:80 与 81.69.144.91:80 的完整双向 HTTP 流（daily.pcapng）。"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")


def parse_pcapng(p):
    d = p.read_bytes()
    i, n = 0, len(d)
    pkts = []
    while i + 8 <= n:
        bt = struct.unpack_from("<I", d, i)[0]
        bl = struct.unpack_from("<I", d, i + 4)[0]
        if bl < 12 or i + bl > n:
            i += 4
            continue
        if bt == 6:
            b = i + 8
            if b + 20 <= n:
                cap = struct.unpack_from("<I", d, b + 12)[0]
                tsh = struct.unpack_from("<I", d, b + 4)[0]
                tsl = struct.unpack_from("<I", d, b + 8)[0]
                pkts.append(((tsh << 32) | tsl, d[b + 20: b + 20 + cap]))
        i += bl
    return pkts


def ipv4(data):
    if len(data) >= 14 and data[12] == 8 and data[13] == 0:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
    return None


def split_tcp(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 0xF) * 4
    hdr = ip[ihl:]
    if len(hdr) < 20:
        return None
    sp = struct.unpack_from(">H", hdr, 0)[0]
    dp = struct.unpack_from(">H", hdr, 2)[0]
    doff = (hdr[12] >> 4) * 4
    return ".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp, hdr[doff:]


def dump_for(pkts, target_ip, target_port):
    req = bytearray()
    resp = bytearray()
    for ts, data in sorted(pkts):
        ip = ipv4(data)
        if not ip:
            continue
        t = split_tcp(ip)
        if not t:
            continue
        sip, sp, dip, dp, pay = t
        if not pay:
            continue
        # client->server
        if sip.startswith("192.168.") and dp == target_port and dip == target_ip:
            req += pay
        elif dip.startswith("192.168.") and sp == target_port and sip == target_ip:
            resp += pay
    print(f"\n========== {target_ip}:{target_port}  REQUEST ({len(req)}B) ==========")
    print(req[:4000].decode("utf-8", "replace"))
    print(f"\n========== {target_ip}:{target_port}  RESPONSE ({len(resp)}B) ==========")
    print(resp[:6000].decode("utf-8", "replace"))


def main():
    pkts = parse_pcapng(ROOT / "daily.pcapng")
    dump_for(pkts, "119.249.103.49", 80)
    dump_for(pkts, "81.69.144.91", 80)
    dump_for(pkts, "111.229.41.195", 80)
    dump_for(pkts, "175.24.235.221", 80)


if __name__ == "__main__":
    main()