import struct

# 官方 1001 body 从 petbag2（完整登录）
pcap = "seer-rebuild/petbag2.pcapng"
SERVER_PORT = 1212  # petbag2 用 1212? 之前是 1230/1212，这里探测
d = open(pcap, "rb").read()
i = 0
# 先找游戏端口
from collections import Counter
ports = Counter()
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
                ports[(sp, dp)] += 1
                break
    i += bl
game_port = None
for (sp, dp), v in ports.most_common():
    if dp not in (443, 80, 53) and dp != sp:
        game_port = dp
        break
print("game_port =", game_port)

# 提取官方 1001 C2S body
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
                if dp == game_port:
                    doff = (pd[o + ihl + 12] >> 4) * 4
                    p = pd[o + ihl + doff:]
                    if p and len(p) >= 17:
                        total = struct.unpack_from(">I", p, 0)[0]
                        if total >= 17 and len(p) >= total:
                            cmd = struct.unpack_from(">I", p, 5)[0]
                            if cmd == 1001:
                                official = p[17:total]
                break
    if official:
        break
    i += bl

from seer_rebuild.login import LoginSession, build_unity_login_body
s = LoginSession(uid=ACCOUNT, session="00" * 16)
mine = build_unity_login_body(s, gate_id=0x699, area_id=1)

print("官方 len", len(official), "我的 len", len(mine))
for base in range(0x10, min(len(official), len(mine)), 16):
    o = official[base:base + 16]
    m = mine[base:base + 16]
    mark = "" if o == m else " <<<"
    print(f"0x{base:02x} 官:{o.hex(' ')}")
    print(f"     我:{m.hex(' ')}{mark}")