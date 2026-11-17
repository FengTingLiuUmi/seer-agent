"""dump lxy_yz_2 的 45543 S2C 完整内容，找 42396 关卡id(111) 与 BOSS species(4938等) 的映射。"""
import struct
from pathlib import Path

P = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\lxy_yz_2.pcapng")


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
    s2c = {}
    for data in parse(P):
        ip = ipv4(data)
        if not ip:
            continue
        t = tcp(ip)
        if not t:
            continue
        meta, pay = t
        sip, sp, dip, dp = meta
        if not pay or not dip.startswith("192.168."):
            continue
        if sp != 1203:
            continue
        s2c.setdefault(sp, bytearray()); s2c[sp] += pay

    for sp, buf in s2c.items():
        for cmd, body in frames(bytes(buf)):
            if cmd != 45543:
                continue
            # 项结构 16 字节：count 后每 16B 一项
            count = struct.unpack_from(">I", body, 0)[0]
            print(f"45543 count={count} len={len(body)} itemsize={(len(body)-4)//count if count else 0}")
            # 每项 dump，标记是否含 111 或 4938
            for k in range(count):
                off = 4 + k * 16
                if off + 16 > len(body):
                    break
                a, b, c, d = struct.unpack_from(">IIII", body, off)
                mark = ""
                if a in (111, 4938) or b in (4938,) or c in (4938,):
                    mark = "  <<< 命中111/4938"
                if k < 20 or mark:
                    print(f"  [{k}] {a} ts={b} {c} {d}{mark}")


if __name__ == "__main__":
    main()