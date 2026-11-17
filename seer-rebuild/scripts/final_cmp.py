"""对比官方 1001 body 与 build_unity_login_body，diff 出关键差异。"""
import struct

# 从 petbag_ws 提取官方 1001 C2S body（服务器端口 1211）
pcap = "seer-rebuild/petbag_ws.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
i = 0
c2s = []
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
                    if p and len(p) >= 17:
                        total = struct.unpack_from(">I", p, 0)[0]
                        if total >= 17 and len(p) >= total and struct.unpack_from(">I", p, 5)[0] == 1001:
                            c2s.append(p[17:total])
                break
    i += bl

official = c2s[0] if c2s else None
print("官方 1001 body len =", len(official) if official else "N/A")

from seer_rebuild.login import LoginSession, build_unity_login_body
# 用官方 session 段（前 16 字节）
sess_hex = official[:16].hex() if official else "00" * 16
s = LoginSession(uid=ACCOUNT, session=sess_hex)
mine = build_unity_login_body(s, gate_id=0x699, area_id=1)

print("对比（逐 16 字节 diff）:")
diffs = 0
for base in range(0, min(len(official), len(mine)), 16):
    o = official[base:base + 16]
    m = mine[base:base + 16]
    mark = "" if o == m else " <<<不同"
    if o != m:
        diffs += 1
    print(f"0x{base:02x} 官:{o.hex(' ')}")
    print(f"     我:{m.hex(' ')}{mark}")
print("总差异块:", diffs)