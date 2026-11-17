"""分析 change_place.pcapng：提取 C2S 时间线，定位“换位/换首发/正式↔待命”的写命令。"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
P = ROOT / "change_place.pcapng"

KNOWN = {3512: "帝皇之御", 3045: "六界神王", 5000: "圣灵谱尼", 3013: "时空界王", 3463: "时空界皇"}


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
    c2s = {}
    for ts, data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        t = tcp(ip)
        if not t:
            continue
        meta, pay = t
        sip, sp, dip, dp = meta
        if not pay or not sip.startswith("192.168."):
            continue
        if not (1200 <= dp <= 1240):
            continue
        key = (dip, dp)
        c2s.setdefault(key, bytearray())
        c2s[key] += pay

    # 已知"读/心跳/登录"命令，用于过滤出新写命令
    known_read = {1001, 1002, 1016, 42494, 43706, 45963, 41228, 41206, 41301, 41345, 42378, 42023, 42105, 1105, 2051, 3401, 3454, 4178, 41870, 41884, 41921, 42406, 42457, 45793, 45824, 45873, 47309, 47334, 47335, 47336, 47343, 40006, 41006, 41185, 4475, 46160, 46046, 42399, 2301, 2361, 2304, 2604, 3404, 9675, 9908, 41253, 43328, 45543}

    for key, buf in c2s.items():
        fs = frames_in(bytes(buf))
        print(f"\n===== {key[0]}:{key[1]}  C2S ({len(fs)} 帧) =====")
        for c, r, b in fs:
            tag = ""
            if c not in known_read:
                tag = "  <<< 新命令"
            if c == 2304:
                # 打印 catch + flag
                if len(b) >= 8:
                    v = struct.unpack_from(">I", b, 0)[0]
                    f = struct.unpack_from(">I", b, 4)[0]
                    sp_name = next((n for k, n in KNOWN.items() if k == v), "")
                    tag += f" [catch=0x{v:x}({sp_name}) flag={f}]"
            print(f"  C2S {c} len={len(b)} body={b[:64].hex()}{tag}")


if __name__ == "__main__":
    main()