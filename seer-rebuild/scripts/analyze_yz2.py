"""分析 lxy_yz_2.pcapng：从第三关到第五关的 C2S 时序 + S2C 关键帧。"""
import struct
from pathlib import Path
from collections import Counter

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
P = ROOT / "lxy_yz_2.pcapng"


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
    doff = (h[12] >> 4) * 4
    return (".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp), h[doff:]


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
    c2s = {}; s2c = {}
    for data in parse(P):
        ip = ipv4(data)
        if not ip:
            continue
        t = tcp(ip)
        if not t:
            continue
        meta, pay = t
        sip, sp, dip, dp = meta
        if not pay:
            continue
        if sip.startswith("192.168.") and (1200 <= dp <= 1240):
            c2s.setdefault((dip, dp), bytearray()); c2s[(dip, dp)] += pay
        elif dip.startswith("192.168.") and (1200 <= sp <= 1240):
            s2c.setdefault((sip, sp), bytearray()); s2c[(sip, sp)] += pay

    for key, buf in c2s.items():
        fs = frames(bytes(buf))
        if not fs:
            continue
        print(f"\n=== C2S {key[0]}:{key[1]} ({len(fs)} 帧) {dict(Counter(c for c,_ in fs))} ===")
        for i, (c, b) in enumerate(fs, 1):
            print(f"  {i:03d} cmd={c} len={len(b)} body={b[:48].hex()}")
    for key, buf in s2c.items():
        fs = frames(bytes(buf))
        if not fs:
            continue
        print(f"\n=== S2C {key[0]}:{key[1]} ({len(fs)} 帧) {dict(Counter(c for c,_ in fs))} ===")
        for c, b in fs:
            if c not in (8002, 3452, 45827, 4395, 8015, 2002, 2001, 1002, 45963):
                print(f"  S2C {c} len={len(b)} body={b[:56].hex()}")


if __name__ == "__main__":
    main()