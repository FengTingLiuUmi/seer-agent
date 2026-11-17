"""粗暴但有效：在 daily.pcapng 所有 TCP 载荷字节里搜关键词，打印上下文。"""
import struct
import re
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")


def parse_pcapng(p):
    d = p.read_bytes()
    i, n = 0, len(d)
    out = []
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
                out.append(d[b + 20: b + 20 + cap])
        i += bl
    return out


def ipv4(data):
    if len(data) >= 14 and data[12] == 0x08 and data[13] == 0x00:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
    return None


def tcp_payload(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None, None
    ihl = (ip[0] & 0xF) * 4
    hdr = ip[ihl:]
    if len(hdr) < 20:
        return None, None
    sp, dp = struct.unpack_from(">H", hdr, 0), struct.unpack_from(">H", hdr, 2)
    doff = (hdr[12] >> 4) * 4
    return (ip[12:16], sp, ip[16:20], dp), hdr[doff:]


def main():
    pkts = parse_pcapng(ROOT / "daily.pcapng")
    # 只关注 80/8080 端口，拼接双向 payload 成一个 blob 搜
    blob = bytearray()
    for data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        meta, payload = tcp_payload(ip)
        if not meta:
            continue
        src, sp, dst, dp = meta
        if dp == 80 or sp == 80 or dp == 8080 or sp == 8080:
            blob += payload

    print("blob len", len(blob))
    kws = [b"61.com", b"seer", b"unity", b"serverid", b"serverId", b"ip.txt", b"authenticate",
           b"online_gate", b"101.35.140.183", b"1229", b"5262", b"//", b"Host:"]
    for kw in kws:
        idxs = [m.start() for m in re.finditer(re.escape(kw), bytes(blob))]
        print(f"\n### {kw!r} x{len(idxs)} ###")
        for s in idxs[:8]:
            ctx = bytes(blob[max(0, s-70):s+150])
            print("   ", ctx.decode("utf-8", "replace").replace("\r", " ").replace("\n", " | "))


if __name__ == "__main__":
    main()