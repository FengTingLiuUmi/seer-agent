"""change_place：把 C2S 写命令(2304/2308/2101) 与 S2C 43706 响应交织，反推 flag 语义。"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
P = ROOT / "change_place.pcapng"
sys = __import__("sys")

from seer_rebuild.battle_data import BattleData
DATA = BattleData(r"F:\seer\seer_cfg\json")


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
        if 17 <= total <= 0x800000 and ver in (0x31, 0x3E) and off + total <= len(buf):
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            out.append((cmd, buf[off + 17:off + total]))
            off += total; continue
        off += 1
    return out


def bag_species(body):
    """用和 parse_bag_43706 相同的块首规则，返回 (count, [species])。"""
    cnt = struct.unpack_from(">I", body, 0)[0] if len(body) >= 4 else 0
    spp = []
    for off in range(0, len(body) - 0x94 - 4):
        s = struct.unpack_from(">I", body, off)[0]
        if not (1 <= s <= 6000) or s not in DATA.species:
            continue
        if body[off + 4:off + 12] != b"\x00" * 8:
            continue
        c = struct.unpack_from(">I", body, off + 0x94)[0]
        if not (0x54A00000 <= c <= 0x6C000000) or (c & 0xFFFF) == 0:
            continue
        if s not in spp:
            spp.append(s)
    return cnt, spp


def main():
    pkts = sorted(parse_pcapng(P))
    ev = []  # (ts, dir, cmd, body)
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
        if (dp if sip.startswith("192.168.") else sp) not in (1201,):
            continue
        if sip.startswith("192.168."):
            key = ("c2s", dip, dp)
            c2s.setdefault(key, bytearray()); c2s[key] += pay
        else:
            key = ("s2c", sip, sp)
            s2c.setdefault(key, bytearray()); s2c[key] += pay

    c2sf = frames_in(bytes(c2s.get(("c2s", "175.24.235.221", 1201), bytearray())))
    s2sf = frames_in(bytes(s2c.get(("s2c", "175.24.235.221", 1201), bytearray())))

    print("=== C2S 写命令（换位相关）===")
    for cmd, body in c2sf:
        if cmd in (2304, 2308, 2101, 2301):
            name = {2304: "PET_RELEASE", 2308: "PET_DEFAULT", 2101: "PEOPLE_WALK/换位?", 2301: "GET_PET_INFO"}[cmd]
            print(f"  C2S {cmd} {name} body={body.hex()}")

    print("\n=== S2C 43706 每次响应的正式/待命 species（按时间）===")
    for cmd, body in s2sf:
        if cmd == 43706:
            cnt, spp = bag_species(body)
            names = [f"{s}({DATA.species[s].name})" for s in spp]
            print(f"  S2C 43706 count={cnt} 正式={names[:cnt]} 待命={names[cnt:]}")


if __name__ == "__main__":
    main()