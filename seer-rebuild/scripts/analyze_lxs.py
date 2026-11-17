"""分析 lxs_pets.pcapng：所有连接的 C2S/S2C，定位背包读取链路。"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
P = ROOT / "lxs_pets.pcapng"

KNOWN = {3512: "帝皇之御", 3045: "六界神王", 5000: "圣灵谱尼", 4050: "时空界神"}


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


def brief(b, n=40):
    note = ""
    if len(b) >= 4:
        head = b[:n].hex()
        # 找已知 species
        for off in range(0, min(len(b) - 3, 600)):
            v = struct.unpack_from(">I", b, off)[0]
            if v in KNOWN:
                note += f" <{KNOWN[v]}@{off:x}>"
    else:
        head = b.hex()
    return head + note


def main():
    pkts = sorted(parse_pcapng(P))
    c2s, s2c = {}, {}
    game_keys = set()
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
        # 只关注游戏端口 1202-1230 与 1863/1864 网关
        port = dp if sip.startswith("192.168.") else sp
        if port not in (1863, 1864) and not (1202 <= port <= 1230):
            continue
        if sip.startswith("192.168."):
            key = (sip, dip, dp)
            c2s.setdefault(key, bytearray())
            c2s[key] += pay
            game_keys.add(key)
        elif dip.startswith("192.168."):
            key = (dip, sip, sp)
            s2c.setdefault(key, bytearray())
            s2c[key] += pay
            game_keys.add(key)

    for key in sorted(game_keys):
        cfs = frames_in(bytes(c2s.get(key, bytearray())))
        sfs = frames_in(bytes(s2c.get(key, bytearray())))
        if not cfs and not sfs:
            continue
        rip = key[1]; rp = key[2]
        print(f"\n========== {rip}:{rp} ==========")
        print(f"  C2S cmds: {sorted({c for c,_,_ in cfs})}")
        print(f"  S2C cmds: {sorted({c for c,_,_ in sfs})}")
        for c, r, b in cfs:
            print(f"    C2S {c} len={len(b)} body={brief(b)}")
        # S2C 只列背包相关 + 已知 species
        for c, r, b in sfs:
            if c in (43706, 2301, 46046, 2361, 2304, 2101, 2001, 2002, 1002, 45963) or any(v in KNOWN for v in (struct.unpack_from('>I', b, o)[0] for o in range(0, min(len(b)-3, 600)) if o % 4 == 0)):
                print(f"    S2C {c} len={len(b)} res={r} body={brief(b)}")


if __name__ == "__main__":
    main()