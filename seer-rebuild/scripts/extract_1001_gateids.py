"""从所有 pcapng 里提取 C2S 1001 body，并把 gate_id/area_id 关联到具体 TCP 流（server ip:port）。

只打印「确实承载了 1001 C2S 帧」的流。
"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")


def parse_pcapng(p: Path):
    d = p.read_bytes()
    i = 0
    pkts = []
    n = len(d)
    while i + 8 <= n:
        bt = struct.unpack_from("<I", d, i)[0]
        bl = struct.unpack_from("<I", d, i + 4)[0]
        if bl < 12 or i + bl > n:
            i += 4
            continue
        if bt == 6:
            body = i + 8
            if body + 20 > n:
                i += 4
                continue
            caplen = struct.unpack_from("<I", d, body + 12)[0]
            data = d[body + 20: body + 20 + caplen]
            pkts.append(data)
        i += bl
    return pkts


def ipv4_from_l2(data: bytes):
    if len(data) >= 14 and data[12] == 0x08 and data[13] == 0x00:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
    return None


def tcp_fields(ip: bytes):
    if len(ip) < 20 or (ip[0] >> 4) != 4:
        return None
    ihl = (ip[0] & 0xF) * 4
    if len(ip) < ihl + 20 or ip[9] != 6:
        return None
    src = ".".join(str(b) for b in ip[12:16])
    dst = ".".join(str(b) for b in ip[16:20])
    tcp = ip[ihl:]
    if len(tcp) < 20:
        return None
    sp = struct.unpack_from(">H", tcp, 0)[0]
    dp = struct.unpack_from(">H", tcp, 2)[0]
    doff = (tcp[12] >> 4) * 4
    payload = tcp[doff:]
    return src, sp, dst, dp, payload


def find_1001_in_stream(buf: bytes):
    """在单个方向的字节流里找所有 cmd=1001 帧 body。"""
    found = []
    off = 0
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]
        ver = buf[off + 4]
        if 17 <= total <= 0x800000 and ver in (0x31, 0x3E, 0x2A, 0x00):
            if off + total <= len(buf):
                cmd = struct.unpack_from(">I", buf, off + 5)[0]
                if cmd == 1001:
                    found.append(buf[off + 17: off + total])
                off += total
                continue
        off += 1
    return found


def main():
    for p in sorted(ROOT.glob("*.pcapng")):
        pkts = parse_pcapng(p)
        # 每条流独立聚合（client->server 方向）
        streams = {}
        for data in pkts:
            ip = ipv4_from_l2(data)
            if not ip:
                continue
            t = tcp_fields(ip)
            if not t:
                continue
            src, sp, dst, dp, payload = t
            if not payload:
                continue
            key = (src, sp, dst, dp)
            streams.setdefault(key, bytearray())
            streams[key] += payload

        printed_header = False
        for (sip, sp, dip, dp), buf in sorted(streams.items()):
            bodies = find_1001_in_stream(bytes(buf))
            if not bodies:
                continue
            if not printed_header:
                print(f"=== {p.name} ===")
                printed_header = True
            for b in bodies:
                gate = struct.unpack_from(">H", b, 0x52)[0] if len(b) > 0x54 else None
                area = struct.unpack_from(">I", b, 0x54)[0] if len(b) > 0x58 else None
                gs = f"0x{gate:04X}({gate})" if gate is not None else "?"
                print(f"  {sip}:{sp} -> {dip}:{dp}  len={len(b)} gate_id={gs} area_id={area}")


if __name__ == "__main__":
    main()