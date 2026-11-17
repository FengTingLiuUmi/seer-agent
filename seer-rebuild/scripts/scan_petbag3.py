"""双向扫描 petbag2 的游戏端口帧，找精灵背包命令（读/放回/加入）。"""
import struct

pcap = "seer-rebuild/petbag2.pcapng"
PORT = 1218
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
                uid = struct.unpack_from(">I", payload, start + 9)[0]
                res = struct.unpack_from(">i", payload, start + 13)[0]
                body = payload[start + 17:start + total]
                frames.append((direction, cmd, res, len(body), body.hex()))
            break
    i += bl

# 去重：连续重复帧合并，只留首次
print(f"原始帧数 {len(frames)}")
seen = {}
for direction, cmd, res, blen, body in frames:
    key = (direction, cmd, body[:24])
    if key not in seen:
        seen[key] = [direction, cmd, res, blen, body, 0]
    seen[key][5] += 1

for direction, cmd, res, blen, body, cnt in seen.values():
    tag = " <<< 写/读关键" if cmd not in (3452, 8002, 45827, 1001, 1016, 4395, 2002) else ""
    print(f"{direction} cmd={cmd} res={res} len={blen} x{cnt}{tag}")
    if cmd not in (3452, 8002, 45827, 1001, 1016, 4395, 2002):
        print(f"     body={body[:140]}")