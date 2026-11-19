import struct
from pathlib import Path
from collections import defaultdict

P = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\reverse\xiwa.pcapng")


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
        return None, None, None
    ihl = (ip[0] & 0xF) * 4; h = ip[ihl:]
    if len(h) < 20:
        return None, None, None
    sp = struct.unpack_from(">H", h, 0)[0]; dp = struct.unpack_from(">H", h, 2)[0]
    doff = (h[12] >> 4) * 4
    sip = ".".join(map(str, ip[12:16])); dip = ".".join(map(str, ip[16:20]))
    return (sip, sp, dip, dp), h[doff:], ip[2:4]


def frames_in(buf):
    off, out = 0, []
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]; ver = buf[off + 4]
        if 17 <= total <= 0x800000 and off + total <= len(buf):
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            res = struct.unpack_from(">i", buf, off + 13)[0]
            out.append((cmd, res, buf[off + 17:off + total]))
            off += total; continue
        off += 1
    return out


def main():
    pkts = sorted(parse_pcapng(P))
    # 按四元组重组成双向流
    streams = defaultdict(bytearray)  # (a,pa,b,pb) -> bytes，按 TCP seq 近似
    for ts, data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        meta, pay, _ = tcp(ip)
        if not meta or not pay:
            continue
        sip, sp, dip, dp = meta
        key = (sip, sp, dip, dp)
        streams[key] += pay

    # 找出远端（游戏服务器）端口
    rports = set()
    for (sip, sp, dip, dp) in streams:
        rports.add(sp if "192.168." not in sip else dp)
    print("远端端口候选:", rports)

    needle = struct.pack(">I", 3865)
    for key, buf in streams.items():
        sip, sp, dip, dp = key
        fs = frames_in(bytes(buf))
        if not fs:
            continue
        direction = "C2S" if "192.168." in sip else "S2C"
        print(f"\n== {direction} {sip}:{sp} -> {dip}:{dp}  {len(fs)} 帧 ==")
        for c, r, b in fs:
            flag = "  <<<3865希瓦" if needle in b else ""
            print(f"  cmd={c} res={r} len={len(b)} body={b[:72].hex()}{flag}")


if __name__ == "__main__":
    main()