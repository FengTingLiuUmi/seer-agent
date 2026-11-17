"""从 daily.pcapng 提取 TLS ClientHello 的 SNI（明文），按时间排序。

用于定位雷小伊登录时在连游戏服之前访问的 HTTPS 域名（区服列表来源）。
"""
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


def tcp_payload(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 0xF) * 4
    h = ip[ihl:]
    if len(h) < 20:
        return None
    sp = struct.unpack_from(">H", h, 0)[0]
    dp = struct.unpack_from(">H", h, 2)[0]
    doff = (h[12] >> 4) * 4
    return (".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp), h[doff:]


def sni(payload):
    # TLS record: [type=0x16][ver][len], then Handshake[0x01][len3][type=0x01(ClientHello)]
    if len(payload) < 6 or payload[0] != 0x16:
        return None
    # 跳过 record header (5 bytes)，进入 handshake
    p = payload[5:]
    if len(p) < 4 or p[0] != 0x01:
        return None
    hslen = int.from_bytes(p[1:4], "big")
    p = p[4:4 + hslen]
    if len(p) < 34 or p[0] != 0x01:
        return None
    # ClientHello: 4 + 32 random + session_id_len(1) + sid + cipher(2) + comp(1) + extlen(2)
    off = 4 + 32
    if len(p) <= off:
        return None
    sidlen = p[off]
    off += 1 + sidlen
    if len(p) < off + 2:
        return None
    cslen = int.from_bytes(p[off:off + 2], "big")
    off += 2 + cslen
    if len(p) < off + 1:
        return None
    complen = p[off]
    off += 1 + complen
    if len(p) < off + 2:
        return None
    extlen = int.from_bytes(p[off:off + 2], "big")
    off += 2
    end = off + extlen
    while off + 4 <= end and off + 4 <= len(p):
        et = int.from_bytes(p[off:off + 2], "big")
        el = int.from_bytes(p[off + 2:off + 4], "big")
        off += 4
        if off + el > len(p):
            break
        if et == 0:  # server_name
            # list len(2) type(1) name len(2) name
            if el >= 5:
                nl = int.from_bytes(p[off + 3:off + 5], "big")
                return p[off + 5:off + 5 + nl].decode("utf-8", "replace")
            return None
        off += el
    return None


def main():
    pkts = sorted(parse_pcapng(ROOT / "daily.pcapng"))
    seen = set()
    t0 = None
    for ts, data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        t = tcp_payload(ip)
        if not t:
            continue
        meta, pay = t
        if not pay:
            continue
        if t0 is None:
            t0 = ts
        # 只看客户端发出的 TLS（ClientHello 里带 SNI）
        if not meta[0].startswith("192.168."):
            continue
        if meta[3] not in (443, 8443, 3008, 3007):
            continue
        s = sni(pay)
        if s:
            key = (meta[2], meta[3], s)
            if key in seen:
                continue
            seen.add(key)
            dt = (ts - t0) / 1e6
            print(f"  +{dt:7.3f}s  {meta[0]}:{meta[1]} -> {meta[2]}:{meta[3]}  SNI={s}")


if __name__ == "__main__":
    main()