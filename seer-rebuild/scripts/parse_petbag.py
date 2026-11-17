"""重组 petbag 抓包的 1230 端口双向流，解析 C2S 与 S2C 帧，找精灵背包响应。"""
import struct
from collections import defaultdict

from seer_rebuild.protocol import FrameSplitter

PORT = 1230
pcap = "seer-rebuild/petbag.pcapng"

d = open(pcap, "rb").read()
endian = "<"
streams = {"C2S": bytearray(), "S2C": bytearray()}
order = []

i = 0
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
            if ihl < 20 or ipoff + ihl + 20 > len(pd):
                continue
            if pd[ipoff + 9] != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            if sp != PORT and dp != PORT:
                break
            doff = (pd[ipoff + ihl + 12] >> 4) * 4
            payload = pd[ipoff + ihl + doff:]
            direction = "C2S" if dp == PORT else "S2C"
            streams[direction].extend(payload)
            order.append(direction)
            break
    i += bl

for direction in ("C2S", "S2C"):
    sp = FrameSplitter("h5")
    try:
        frames = sp.push(bytes(streams[direction]))
    except Exception as e:
        print(f"{direction} parse error: {e}")
        continue
    print(f"\n=== {direction} ({len(frames)} 帧) ===")
    seen = set()
    for f in frames:
        key = (f.cmd,)
        tag = "" if key in seen else "  <-- 新命令"
        seen.add(key)
        print(f"  cmd={f.cmd:6d} ver={hex(f.version or 0)} result={f.result:4d} len={len(f.body):4d} {tag}")
        if f.cmd not in (3452, 8002, 45827):
            print(f"      body={f.body[:80].hex()}")