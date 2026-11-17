import struct

# 官方 1001 C2S body（从 wsbag 抓包）
pcap = "seer-rebuild/wsbag.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
i = 0
official = None
while i + 8 <= len(d):
    bt, bl = struct.unpack_from("<II", d, i)
    if bl < 8 or i + bl > len(d):
        i += 4
        continue
    if bt == 6:
        off = i + 8
        cap = struct.unpack_from("<I", d, off + 16)[0]
        pd = d[off + 24:off + 24 + cap]
        for o in range(0, min(len(pd) - 40, 64)):
            if len(pd) < o + 40:
                break
            if pd[o] >> 4 != 4:
                continue
            ihl = (pd[o] & 15) * 4
            if pd[o + 9] == 6:
                sp, dp = struct.unpack_from(">HH", pd, o + ihl)
                if dp == SERVER_PORT:
                    doff = (pd[o + ihl + 12] >> 4) * 4
                    p = pd[o + ihl + doff:]
                    if not p or len(p) < 8:
                        break
                    total = struct.unpack_from(">I", p, 0)[0]
                    ver = p[4]
                    cmd = struct.unpack_from(">I", p, 5)[0]
                    if cmd == 1001 and total >= 17 and len(p) >= total:
                        official = p[17:17 + (total - 17)]
                    break
    if official:
        break
    i += bl

# 我的 build_unity_login_body
from seer_rebuild.login import LoginSession, build_unity_login_body
s = LoginSession(uid=ACCOUNT, session="00" * 16)
mine = build_unity_login_body(s, gate_id=0x699, area_id=1)

print("官方 1001 body len =", len(official), "我的 =", len(mine))
print("\n字段对比（前 0xb0 字节）：")
for base in range(0, 0xB0, 16):
    o = official[base:base + 16]
    m = mine[base:base + 16]
    mark = "" if o == m else "  <<<不同"
    print(f"0x{base:02x} 官:{o.hex(' ')}")
    print(f"     我:{m.hex(' ')}{mark}")