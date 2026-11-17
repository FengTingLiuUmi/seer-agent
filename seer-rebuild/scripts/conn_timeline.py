"""列出 daily.pcapng 里按时间排序的 TCP 连接建立（SYN）事件，标注远端 IP:port。

用于还原「雷小伊登录 → 拿区服列表 → 连游戏服」的连接顺序。
"""
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")


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
            body = i + 8
            if body + 20 <= n:
                cap = struct.unpack_from("<I", d, body + 12)[0]
                tsh = struct.unpack_from("<I", d, body + 4)[0]
                tsl = struct.unpack_from("<I", d, body + 8)[0]
                ts = (tsh << 32) | tsl
                pkts.append((ts, d[body + 20: body + 20 + cap]))
        i += bl
    return pkts


def ipv4(data):
    if len(data) >= 14 and data[12] == 0x08 and data[13] == 0x00:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
    return None


def tcp_meta(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 0xF) * 4
    t = ip[ihl:]
    if len(t) < 20:
        return None
    sp, dp = struct.unpack_from(">H", t, 0), struct.unpack_from(">H", t, 2)
    flags = t[13]
    return (".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp, flags)


def main():
    pkts = sorted(parse_pcapng(ROOT / "daily.pcapng"))
    # 去重：每个 4 元组只记第一次 SYN
    seen = set()
    t0 = None
    for ts, data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        m = tcp_meta(ip)
        if not m:
            continue
        sip, sp, dip, dp, flags = m
        if flags & 0x02 == 0:  # 只看 SYN
            continue
        # 只看「本机 ↔ 外部」且外部不是 443(HTTPS 噪声) 的连接
        # 本机网段 192.168.112.137
        local = None
        remote = None
        if sip.startswith("192.168."):
            local, remote = (sip, sp), (dip, dp)
        elif dip.startswith("192.168."):
            local, remote = (dip, dp), (sip, sp)
        else:
            continue
        key = (local, remote)
        if key in seen:
            continue
        seen.add(key)
        if t0 is None:
            t0 = ts
        dt = (ts - t0) / 1e6
        # 过滤明显无关的端口
        if remote[1] in (443, 80, 8080, 53, 5228, 27018, 7826):
            continue
        print(f"  +{dt:8.3f}s  {local[0]}:{local[1]} -> {remote[0]}:{remote[1]}")


if __name__ == "__main__":
    main()