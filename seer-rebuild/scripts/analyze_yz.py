"""分析 lxy_yz.pcapng：C2S 时序 + S2C 分布（重点看战斗观测帧）。"""
import struct
from pathlib import Path
from collections import Counter

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
P = ROOT / "lxy_yz.pcapng"


def parse_pcapng(p):
    d = p.read_bytes(); i = 0; n = len(d); pkts = []
    while i + 8 <= n:
        bt = struct.unpack_from("<I", d, i)[0]; bl = struct.unpack_from("<I", d, i + 4)[0]
        if bl < 12 or i + bl > n:
            i += 4; continue
        if bt == 6:
            b = i + 8
            if b + 20 <= n:
                cap = struct.unpack_from("<I", d, b + 12)[0]
                tsh = struct.unpack_from("<I", d, b + 4)[0]; tsl = struct.unpack_from("<I", d, b + 8)[0]
                pkts.append(((tsh << 32) | tsl, d[b + 20:b + 20 + cap]))
        i += bl
    return pkts


def ipv4(data):
    if len(data) >= 14 and data[12] == 8 and data[13] == 0:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
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


def frames_in(buf):
    off, out = 0, []
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]; ver = buf[off + 4]
        if 17 <= total <= 0x800000 and ver in (0x31, 0x3E, 0x2A) and off + total <= len(buf):
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            res = struct.unpack_from(">i", buf, off + 13)[0]
            out.append((cmd, res, buf[off + 17:off + total]))
            off += total; continue
        off += 1
    return out


def main():
    pkts = sorted(parse_pcapng(P))
    c2s = {}; s2c = {}
    for ts, data in pkts:
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
        if sip.startswith("192.168."):
            c2s.setdefault((dip, dp), bytearray()); c2s[(dip, dp)] += pay
        elif dip.startswith("192.168."):
            s2c.setdefault((sip, sp), bytearray()); s2c[(sip, sp)] += pay

    print("=== 游戏连接 C2S + S2C 帧分布 ===")
    for key, buf in c2s.items():
        if key[1] not in (1203, 1205, 1278):
            continue
        fs = frames_in(bytes(buf))
        if not fs:
            continue
        print(f"\n[{key[0]}:{key[1]}] C2S {len(fs)} 帧: {dict(Counter(c for c,_,_ in fs))}")
    for key, buf in s2c.items():
        if key[1] not in (1203, 1205, 1278):
            continue
        fs = frames_in(bytes(buf))
        if not fs:
            continue
        print(f"\n[{key[0]}:{key[1]}] S2C {len(fs)} 帧: {dict(Counter(c for c,_,_ in fs))}")

    # 主连接 1203 的 S2C 战斗关键帧
    print("\n=== 101.34.70.151:1203 S2C 关键帧（战斗观测候选）===")
    for key, buf in s2c.items():
        if key != ("101.34.70.151", 1203):
            continue
        for c, r, b in frames_in(bytes(buf)):
            if c in (2408, 2404, 2405, 2419, 2004, 3401, 2341, 2301, 43706, 45543, 46046, 42399, 2604, 3404, 2304, 2001, 2002, 2101, 9019, 41413, 41206, 45555):
                print(f"  S2C {c} len={len(b)} res={r} body={b[:40].hex()}")


if __name__ == "__main__":
    main()