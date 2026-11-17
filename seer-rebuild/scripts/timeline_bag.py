"""从背包抓包里按 TCP 连接重组双向帧，输出 C2S/S2C 合并时间线。

用于定位：43706 只含 3 只（3512/3045/5000），第 4 只时空界神(4050) 从哪条命令回来。
"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

KNOWN = {3512: "帝皇之御", 3045: "六界神王", 5000: "圣灵谱尼", 4050: "时空界神"}


def parse_pcapng(p: Path):
    d = p.read_bytes()
    i, n = 0, len(d)
    pkts = []
    while i + 8 <= n:
        bt = struct.unpack_from("<I", d, i)[0]
        bl = struct.unpack_from("<I", d, i + 4)[0]
        if bl < 12 or i + bl > n:
            i += 4
            continue
        if bt == 6:
            b = i + 8
            if b + 20 <= n:
                cap = struct.unpack_from("<I", d, b + 12)[0]
                tsh = struct.unpack_from("<I", d, b + 4)[0]
                tsl = struct.unpack_from("<I", d, b + 8)[0]
                ts = (tsh << 32) | tsl
                pkts.append((ts, d[b + 20:b + 20 + cap]))
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
    ihl = (ip[0] & 0xF) * 4
    h = ip[ihl:]
    if len(h) < 20:
        return None
    sp = struct.unpack_from(">H", h, 0)[0]
    dp = struct.unpack_from(">H", h, 2)[0]
    doff = (h[12] >> 4) * 4
    return (".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp), h[doff:]


def frames_in(buf):
    off, out = 0, []
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
        pkts = sorted(parse_pcapng(p))
        # 按 4 元组聚合双向 payload（客户端 192.168.x）
        c2s = {}
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
            if not pay:
                continue
            if sip.startswith("192.168."):
                key = (sip, dip, dp)  # 以远端 ip:port 标识连接
                c2s.setdefault(key, bytearray())
                c2s[key] += pay
            elif dip.startswith("192.168."):
                key = (dip, sip, sp)
                s2c.setdefault(key, bytearray())
                s2c[key] += pay

        print(f"\n===== {fn} =====")
        # 对每个连接，找有 1001/43706 的游戏连接
        for key, buf in c2s.items():
            fs = frames_in(bytes(buf))
            cmds = {c for c, _, _ in fs}
            if 1001 not in cmds and 43706 not in cmds and 46046 not in cmds:
                continue
            remote_ip, remote_port = key[1], key[2]
            print(f"\n--- 连接 {remote_ip}:{remote_port} ---")
            print(f"  C2S cmds: {sorted(cmds)}")
            print("  [C2S 时序/顺序]")
            for c, r, b in fs:
                hint = ""
                v = struct.unpack_from(">I", b, 0)[0] if len(b) >= 4 else None
                if c in (2301, 46046) and v in KNOWN:
                    hint = f" species={v}({KNOWN[v]})"
                print(f"    C2S cmd={c} len={len(b)} body={b[:32].hex()}{hint}")
            # 对应 S2C
            sfs = frames_in(bytes(s2c.get(key, bytearray())))
            print(f"  S2C cmds: {sorted({c for c,_,_ in sfs})}")
            print("  [S2C 时序/顺序，仅列关键]")
            for c, r, b in sfs:
                hint = ""
                # 找 body 里出现已知 species 或 catch 的位置
                for off in range(0, min(len(b) - 3, 260), 4):
                    v = struct.unpack_from(">I", b, off)[0]
                    if v in KNOWN:
                        hint += f" species={v}({KNOWN[v]})@+0x{off:x}"
                if c in (2301, 2361, 43706, 46046):
                    print(f"    S2C cmd={c} len={len(b)} res={r} body={b[:40].hex()}{hint}")
            print()


if __name__ == "__main__":
    main()