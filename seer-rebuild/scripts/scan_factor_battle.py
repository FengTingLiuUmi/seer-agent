"""扫描 factor_write_only / daily 两个大包，找 2604/3404(切换装备称号) 与战斗帧(2404/2405/2408/2419/2004)。"""
import struct
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

WANT_C2S = {2604, 3404, 2404, 2405, 2408, 2419, 2004, 41413, 46046, 45543, 2304, 2001, 2101, 2301, 2308, 45555}
WANT_S2C = {2604, 3404, 2404, 2405, 2408, 2419, 2004, 2101, 2301, 2361, 43706, 45866, 45555, 9019, 40001, 45807}


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


def scan(path, ports=(1200,), limit=200):
    game_c2s = {}; game_s2c = {}
    for data in parse(path):
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
            game_c2s.setdefault((dip, dp), bytearray()); game_c2s[(dip, dp)] += pay
        elif dip.startswith("192.168.") and (1200 <= sp <= 1240):
            game_s2c.setdefault((sip, sp), bytearray()); game_s2c[(sip, sp)] += pay

    print(f"\n===== {path.name} =====")
    for key, buf in game_c2s.items():
        fs = frames(bytes(buf))
        dist = Counter(c for c, _ in fs)
        print(f"  C2S {key[0]}:{key[1]} {len(fs)}帧: {dict(dist)}")
        for c, b in fs:
            if c in WANT_C2S:
                print(f"      C2S {c} len={len(b)} body={b[:48].hex()}")
    for key, buf in game_s2c.items():
        fs = frames(bytes(buf))
        dist = Counter(c for c, _ in fs)
        print(f"  S2C {key[0]}:{key[1]} {len(fs)}帧: {dict(dist)}")
        for c, b in fs:
            if c in WANT_S2C:
                print(f"      S2C {c} len={len(b)} body={b[:48].hex()}")


if __name__ == "__main__":
    scan(ROOT / "factor_write_only.pcapng")
    scan(ROOT / "daily.pcapng")