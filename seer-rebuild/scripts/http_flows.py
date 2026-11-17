"""Reassemble daily.pcapng 的明文 TCP 流，打印 port 80 的 HTTP 头 + 含游戏 IP/端口的响应体。"""
import struct
import re
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
                pkts.append(d[body + 20: body + 20 + cap])
        i += bl
    return pkts


def ipv4(data):
    if len(data) >= 14 and data[12] == 0x08 and data[13] == 0x00:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
    return None


def tcp(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4 or ip[9] != 6:
        return None
    ihl = (ip[0] & 0xF) * 4
    hdr = ip[ihl:]
    if len(hdr) < 20:
        return None
    sp, dp = struct.unpack_from(">H", hdr, 0), struct.unpack_from(">H", hdr, 2)
    doff = (hdr[12] >> 4) * 4
    return ip[12:16], sp, ip[16:20], dp, hdr[doff:]


def main():
    pkts = parse_pcapng(ROOT / "daily.pcapng")
    flows = {}
    order = []
    for data in pkts:
        ip = ipv4(data)
        if not ip:
            continue
        t = tcp(ip)
        if not t:
            continue
        sip, sp, dip, dp, payload = t
        if not payload:
            continue
        # 双向方向区分：以「客户端 192.168 → 远端」为请求，反之为响应
        if sip.startswith(b"192.168."):
            key = ("req", sip, sp, dip, dp)
        elif dip.startswith(b"192.168."):
            key = ("resp", dip, dp, sip, sp)
        else:
            continue
        if key not in flows:
            flows[key] = bytearray()
            order.append(key)
        flows[key] += payload

    # 打印 port 80 的请求行 + Host + 前几个路径
    print("### HTTP(80) requests ###")
    for key in order:
        d, role = key, key[0]
        if role != "req" or key[4] != 80:
            continue
        buf = bytes(flows[key])
        if not (buf.startswith((b"GET", b"POST", b"HEAD", b"PUT"))):
            continue
        head = buf[:800]
        m = re.search(rb"([A-Z]+) ([^ ]+) HTTP/1", head)
        hm = re.search(rb"[Hh]ost:\s*([^\r\n]+)", head)
        if not m:
            continue
        print(f"  [{key[2]}:{key[3]} -> {key[4]}:{key[5]}]")
        print(f"    {m.group(1).decode()}  host={hm.group(1).decode(errors='replace') if hm else '?'}  path={m.group(2).decode(errors='replace')[:160]}")

    # 打印含游戏 IP 或 serverid 的响应体片段
    print("\n### HTTP(80) responses mentioning game IP / serverid / 1200s ###")
    pat = re.compile(rb"(serverid|serverId|101\.35\.140\.183|175\.24\.235\.221|111\.229\.[0-9.]+|49\.235\.76\.189|101\.43\.76\.68|12[0-9][0-9])")
    for key in order:
        if key[0] != "resp":
            continue
        buf = bytes(flows[key])
        # 跳过连接建立后的响应头，找 body 里的关键词
        for m in pat.finditer(buf):
            s = m.start()
            ctx = buf[max(0, s-80):s+160]
            print(f"  [{key[2]}:{key[3]} <- {key[4]}:{key[5]}] ...{ctx.decode('utf-8', 'replace')!r}")
            break


if __name__ == "__main__":
    main()