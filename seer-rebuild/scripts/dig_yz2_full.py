"""按 TCP seq 正确重组 lxy_yz_2，完整提取 C2S/S2C 帧（避免简单拼接漏帧）。"""
import struct
from pathlib import Path
from collections import Counter

P = Path(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\lxy_yz_2.pcapng")


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


def tcp_hdr(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 0xF) * 4; h = ip[ihl:]
    if len(h) < 20:
        return None
    sp = struct.unpack_from(">H", h, 0)[0]; dp = struct.unpack_from(">H", h, 2)[0]
    seq = struct.unpack_from(">I", h, 4)[0]
    doff = (h[12] >> 4) * 4
    return (".".join(map(str, ip[12:16])), sp, ".".join(map(str, ip[16:20])), dp, seq), h[doff:]


def reassemble(pkts, ports):
    """按四元组+seq 重组双向 payload。"""
    segs = {}  # (sip,sp,dip,dp) -> {seq: payload}
    for data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        th = tcp_hdr(ip)
        if not th:
            continue
        (sip, sp, dip, dp, seq), payload = th
        if not payload:
            continue
        if sip.startswith("192.168.") and dp in ports:
            key = (sip, sp, dip, dp)
        elif dip.startswith("192.168.") and sp in ports:
            key = (dip, dp, sip, sp)
        else:
            continue
        segs.setdefault(key, {})[seq] = payload
    # 按 seq 排序拼接
    out = {}
    for key, m in segs.items():
        buf = bytearray()
        for seq in sorted(m):
            buf += m[seq]
        out[key] = bytes(buf)
    return out


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
    pkts = parse(P)
    streams = reassemble(pkts, set(range(1200, 1241)))
    c2s = {}; s2c = {}
    for key, buf in streams.items():
        if key[1] > key[3]:  # 端口判方向不可靠，改用 client 判断
            pass
        # key = (client_ip, client_port, server_ip, server_port) 按构造方式
        # 构造时 client->server: key=(client_ip,cp,server_ip,sp)；server->client: key=(client_ip,cp,server_ip,sp) 同样
        c2s[(key[0], key[2], key[3])] = buf

    # 直接按 IP:port 分组打印统计
    for key, buf in streams.items():
        fs = frames(buf)
        # 区分方向：发端是 192.168 还是收端
        pass


# 简化：直接输出每条流的帧数和命令分布
def main2():
    pkts = parse(P)
    # 方向标记
    c2s = {}; s2c = {}
    for data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        th = tcp_hdr(ip)
        if not th:
            continue
        sip, sp, dip, dp, seq = th[0]
        _, payload = th
        # 重新拿 payload
        ih = ip[( (ip[0]&0xF)*4 ):]
        # 直接跳过，重写
        break


if __name__ == "__main__":
    # 用最简单的：按 4 元组 + seq 重组，但保留方向
    pkts = parse(P)
    c2s = {}; s2c = {}
    for data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
            continue
        ihl = (ip[0] & 0xF) * 4
        h = ip[ihl:]
        if len(h) < 20:
            continue
        sp = struct.unpack_from(">H", h, 0)[0]; dp = struct.unpack_from(">H", h, 2)[0]
        seq = struct.unpack_from(">I", h, 4)[0]
        doff = (h[12] >> 4) * 4
        payload = h[doff:]
        if not payload:
            continue
        sip = ".".join(map(str, ip[12:16])); dip = ".".join(map(str, ip[16:20]))
        if sip.startswith("192.168.") and (1200 <= dp <= 1240):
            key = (dip, dp)
            c2s.setdefault(key, {})[seq] = payload
        elif dip.startswith("192.168.") and (1200 <= sp <= 1240):
            key = (sip, sp)
            s2c.setdefault(key, {})[seq] = payload

    for key, m in c2s.items():
        buf = bytearray()
        for s in sorted(m):
            buf += m[s]
        fs = frames(bytes(buf))
        print(f"\n=== C2S {key[0]}:{key[1]} ({len(fs)} 帧) {dict(Counter(c for c,_ in fs))} ===")
        for i, (c, b) in enumerate(fs, 1):
            if c in (42396, 2404, 2405, 47136, 2304, 43706, 45543, 41306, 11187, 45767, 42395, 42396, 41129):
                print(f"  {i:03d} cmd={c} len={len(b)} body={b[:48].hex()}")
    for key, m in s2c.items():
        buf = bytearray()
        for s in sorted(m):
            buf += m[s]
        fs = frames(bytes(buf))
        cnt = Counter(c for c, _ in fs)
        print(f"\n=== S2C {key[0]}:{key[1]} ({len(fs)} 帧) {dict(cnt)} ===")
        # 高亮与因子关/结算相关的
        for c, b in fs:
            if c in (2506, 41306, 4549, 11187, 42396, 2404, 2405, 47136, 45767, 42395, 41129, 41306):
                print(f"  S2C {c} len={len(b)} body={b[:56].hex()}")