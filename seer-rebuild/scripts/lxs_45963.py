"""精确提取 lxs_pets 里所有 S2C 45963 单只推送的 species@0x74 + catch@0x34。"""
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


def main():
    pkts = sorted(parse_pcapng(P))
    s2c = {}
    for ts, data in pkts:
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
        if sp not in (1202, 1203):
            continue
        key = (dip, sip, sp)
        s2c.setdefault(key, bytearray())
        s2c[key] += pay

    for key, buf in s2c.items():
        rip, rp = key[1], key[2]
        pushes = []
        for c, r, b in frames_in(bytes(buf)):
            if c == 45963 and len(b) > 4:
                species = struct.unpack_from(">I", b, 0x74)[0] if len(b) > 0x78 else None
                catch = struct.unpack_from(">I", b, 0x34)[0] if len(b) > 0x38 else None
                pushes.append((species, catch, b))
        if pushes:
            print(f"\n===== {rip}:{rp}  S2C 45963 单只推送 ({len(pushes)} 条) =====")
            for species, catch, b in pushes:
                print(f"  species@0x74 = {species} ({KNOWN.get(species, '?')})  catch@0x34 = {hex(catch) if catch else '?'}  len={len(b)}")
            # 也 dump 一条的 @0x30-0x80 看看结构
            if pushes:
                b = pushes[0][2]
                print("  首条 0x30-0x80:", b[0x30:0x80].hex())


if __name__ == "__main__":
    main()