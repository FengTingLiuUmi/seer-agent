import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")


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


def ipv4(d):
    if len(d) >= 14 and d[12] == 8 and d[13] == 0:
        return d[14:]
    if len(d) >= 4 and (d[0] >> 4) == 4:
        return d
    return None


def tcp(ip):
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


def find_1001(buf):
    off, out = 0, []
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]
        ver = buf[off + 4]
        if 17 <= total <= 0x800000 and ver == 0x31 and off + total <= len(buf):
            if struct.unpack_from(">I", buf, off + 5)[0] == 1001:
                out.append(buf[off + 17:off + total])
            off += total
            continue
        off += 1
    return out


for fn in ["unity_all.pcapng", "petbag_ws.pcapng", "petbag3.pcapng"]:
    p = ROOT / fn
    if not p.exists():
        continue
    print("=====", fn)
    streams = {}
    for data in parse(p):
        ip = ipv4(data)
        if not ip:
            continue
        t = tcp(ip)
        if not t:
            continue
        meta, pay = t
        sip, sp, dip, dp = meta
        if sip.startswith("192.168.") and pay:
            streams.setdefault((dip, dp), bytearray())
            streams[(dip, dp)] += pay
    for (dip, dp), buf in streams.items():
        for b in find_1001(bytes(buf)):
            print(f"  {dip}:{dp} len={len(b)}")
            for base in range(0x40, 0x60, 8):
                print(f"    0x{base:02x}: {b[base:base+8].hex()}")
            print(f"    u16@0x4c={struct.unpack_from('>H',b,0x4c)[0]:#06x}"
                  f" u32@0x50={struct.unpack_from('>I',b,0x50)[0]:#010x}"
                  f" u16@0x52={struct.unpack_from('>H',b,0x52)[0]:#06x}"
                  f" u16@0x54={struct.unpack_from('>H',b,0x54)[0]:#06x}"
                  f" u32@0x54={struct.unpack_from('>I',b,0x54)[0]}")
            break