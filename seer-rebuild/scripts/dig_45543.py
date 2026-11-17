"""深挖 lxy_yz 的 S2C 45543(关卡列表) / 46046(因子信息) 完整 body，反推进度映射。"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
P = ROOT / "lxy_yz.pcapng"


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
        if sp not in (1203, 1205):
            continue
        s2c.setdefault((sip, sp), bytearray()); s2c[(sip, sp)] += pay

    for key, buf in s2c.items():
        for cmd, body in frames(bytes(buf)):
            if cmd not in (45543, 46046):
                continue
            print(f"\n=== S2C cmd={cmd} len={len(body)} ===")
            # 按 u32 拆解，且打印 [count][项] 结构
            print("  全文 u32 序列：")
            for i in range(0, min(len(body), 0x100), 4):
                v = struct.unpack_from(">I", body, i)[0]
                print(f"    +0x{i:03x}: {v} ({v:#x})")
            if len(body) > 0x100:
                print(f"    ...（共 {len(body)} 字节，{len(body)//4} 个 u32）")


if __name__ == "__main__":
    main()