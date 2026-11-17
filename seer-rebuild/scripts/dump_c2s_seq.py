"""从 wsbag.pcapng / petbag_ws.pcapng 提取 C2S 帧序列（cmd + body），还原打开背包的真实握手。"""
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
                tsh = struct.unpack_from("<I", d, b + 4)[0]
                tsl = struct.unpack_from("<I", d, b + 8)[0]
                pkts.append(((tsh << 32) | tsl, d[b + 20:b + 20 + cap]))
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


def frames_in(buf, c2s=True):
    off = 0
    out = []
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]
        ver = buf[off + 4]
        if 17 <= total <= 0x800000 and ver in (0x31, 0x3E, 0x2A) and off + total <= len(buf):
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            res = struct.unpack_from(">i", buf, off + 13)[0]
            out.append((cmd, res, buf[off + 17:off + total]))
            off += total
            continue
        off += 1
    return out


def main():
    for fn in ["wsbag.pcapng", "petbag_ws.pcapng"]:
        p = ROOT / fn
        if not p.exists():
            continue
        # 客户端→服务器 方向
        c2s_buf = bytearray()
        all_frames = []
        for ts, data in sorted(parse(p)):
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
                c2s_buf += pay
        print(f"===== {fn}  C2S frames (client->server) =====")
        for cmd, res, body in frames_in(bytes(c2s_buf)):
            print(f"  cmd={cmd} len={len(body)} body={body[:40].hex()}")


if __name__ == "__main__":
    main()