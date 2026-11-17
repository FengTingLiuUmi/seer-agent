"""分析 lxy_yz_3.pcapng（另一因子关 + 最后一关失败 case）。"""
import struct
from pathlib import Path
from collections import Counter

P = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\lxy_yz_3.pcapng")


def parse(p):
    d = p.read_bytes(); i = 0; n = len(d); pkts = []
    while i + 8 <= n:
        bt = struct.unpack_from("<I", d, i)[0]; bl = struct.unpack_from("<I", d, i + 4)[0]
        if bl < 12 or i + bl > n:
            i += 4; continue
        if bt == 6:
            b = i + 8
            if b + 20 <= n:
                cap = struct.unpack_from("<I", d, b + 12)[0]
                pkts.append(d[b + 20:b + 20 + cap])
        i += bl
    return pkts


def ipv4(x):
    if len(x) >= 14 and x[12] == 8 and x[13] == 0:
        return x[14:]
    if len(x) >= 4 and (x[0] >> 4) == 4:
        return x
    return None


def tcp(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 0xF) * 4; h = ip[ihl:]
    if len(h) < 20:
        return None
    sp = struct.unpack_from(">H", h, 0)[0]; dp = struct.unpack_from(">H", h, 2)[0]
    seq = struct.unpack_from(">I", h, 4)[0]
    doff = (h[12] >> 4) * 4
    return (".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp, seq), h[doff:]


def reassemble(pkts, lo, hi):
    segs = {}
    for data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        th = tcp(ip)
        if not th:
            continue
        (sip, sp, dip, dp, seq), pay = th
        if not pay:
            continue
        if sip.startswith("192.168.") and lo <= dp <= hi:
            key = ("c2s", dip, dp)
        elif dip.startswith("192.168.") and lo <= sp <= hi:
            key = ("s2c", sip, sp)
        else:
            continue
        segs.setdefault(key, {})[seq] = pay
    out = {}
    for key, m in segs.items():
        buf = bytearray()
        for s in sorted(m):
            buf += m[s]
        out[key] = bytes(buf)
    return out


def frames(buf):
    off, out = 0, []
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]; ver = buf[off + 4]
        if 17 <= total <= 0x800000 and ver in (0x31, 0x3E) and off + total <= len(buf):
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            out.append((cmd, buf[off + 17:off + total]))
            off += total; continue
        off += 1
    return out


def main():
    streams = reassemble(parse(P), 1200, 1240)
    for key, buf in streams.items():
        fs = frames(buf)
        print(f"\n=== {key[0]} {key[1]}:{key[2]} ({len(fs)} 帧) {dict(Counter(c for c,_ in fs))} ===")
        for i, (c, b) in enumerate(fs, 1):
            if key[0] == "c2s":
                if c in (42396, 2404, 2405, 47136, 2304, 43706, 45543, 45767, 42395, 41129, 2406):
                    print(f"  {i:03d} C2S {c} len={len(b)} body={b[:48].hex()}")
            else:
                if c in (2506, 41306, 4549, 11187, 42396, 2404, 2405, 47136, 42395, 41129, 2503, 2504, 2505, 0):
                    print(f"  {i:03d} S2C {c} len={len(b)} body={b[:64].hex()}")


if __name__ == "__main__":
    main()