"""从 pcapng 提取 HTTP 请求行 / Host / 响应体中的候选区服列表。

对明文 TCP（80/8080/7826 等）重组双向流，抓 HTTP 请求与响应，
并把「响应体里出现了 11x~12x 端口 或 101.x/175.x 等游戏 IP」的片段打出来。
"""
import re
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
                caplen = struct.unpack_from("<I", d, body + 12)[0]
                pkts.append(d[body + 20: body + 20 + caplen])
        i += bl
    return pkts


def ipv4(data):
    if len(data) >= 14 and data[12] == 0x08 and data[13] == 0x00:
        return data[14:]
    if len(data) >= 4 and (data[0] >> 4) == 4:
        return data
    return None


def tcp(ip):
    if len(ip) < 20 or (ip[0] >> 4) != 4:
        return None
    ihl = (ip[0] & 0xF) * 4
    if ip[9] != 6 or len(ip) < ihl + 20:
        return None
    hdr = ip[ihl:]
    sp, dp = struct.unpack_from(">H", hdr, 0), struct.unpack_from(">H", hdr, 2)
    doff = (hdr[12] >> 4) * 4
    return ip[12:16], sp, ip[16:20], dp, hdr[doff:]


def main():
    p = ROOT / "daily.pcapng"
    pkts = parse_pcapng(p)
    # 双向流
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
        key = (sip, sp, dip, dp)
        if key not in flows:
            flows[key] = bytearray()
            order.append(key)
        flows[key] += payload

    # 打印 HTTP 请求行（GET/POST）与 Host
    print("### HTTP REQUESTS (method + host + path) ###")
    n_req = 0
    for key in order:
        buf = bytes(flows[key])
        if not buf.startswith(b"GET ") and not buf.startswith(b"POST ") and not buf.startswith(b"PUT "):
            continue
        head = buf[:512]
        m = re.match(rb"([A-Z]+) ([^ ]+) HTTP", head)
        if not m:
            continue
        method, path = m.group(1).decode(), m.group(2).decode(errors="replace")
        hm = re.search(rb"[Hh]ost:\s*(\S+)", head)
        host = hm.group(1).decode(errors="replace") if hm else "?"
        print(f"  {method} http://{host}{path}")
        n_req += 1
        if n_req >= 300:
            break
    print(f"  (total shown {n_req})")


if __name__ == "__main__":
    main()