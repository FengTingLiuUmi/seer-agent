"""双向扫描 Wireshark pcapng（端口 1211），重点解析 S2C 的精灵列表。"""
import struct
from collections import Counter

pcap = "seer-rebuild/petbag_ws.pcapng"
PORT = 1211
d = open(pcap, "rb").read()
endian = "<"
i = 0
frames = []
while i + 8 <= len(d):
    bt, bl = struct.unpack_from(endian + "II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from(endian + "I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        for ipoff in range(0, min(len(pd) - 40, 64)):
            if len(pd) < ipoff + 40:
                break
            if pd[ipoff] >> 4 != 4:
                continue
            ihl = (pd[ipoff] & 15) * 4
            if pd[ipoff + 9] != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            if sp != PORT and dp != PORT:
                break
            doff = (pd[ipoff + ihl + 12] >> 4) * 4
            payload = pd[ipoff + ihl + doff:]
            direction = "S2C" if sp == PORT else "C2S"
            for start in range(0, max(1, len(payload) - 16)):
                total = struct.unpack_from(">I", payload, start)[0]
                if total < 17 or total > 0x800000 or start + total > len(payload):
                    continue
                ver = payload[start + 4]
                if ver not in (0x31, 0x3E):
                    continue
                cmd = struct.unpack_from(">I", payload, start + 5)[0]
                res = struct.unpack_from(">i", payload, start + 13)[0]
                body = payload[start + 17:start + total]
                frames.append((direction, cmd, res, len(body), body.hex()))
            break
    i += bl

print(f"原始帧数 {len(frames)}")
s2c = Counter(); c2s = Counter()
for direction, cmd, res, blen, body in frames:
    (s2c if direction == "S2C" else c2s)[cmd] += 1
print("C2S:", dict(c2s.most_common(25)))
print("S2C:", dict(s2c.most_common(30)))

# 打印 S2C 大帧的 body 前 120 字节
print("\n=== S2C 大帧样本 ===")
seen = set()
for direction, cmd, res, blen, body in frames:
    if direction == "S2C" and cmd not in (3452, 45827) and cmd not in seen:
        seen.add(cmd)
        print(f"S2C cmd={cmd} len={blen} body={body[:140]}")