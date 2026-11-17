import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
d = open(pcap, "rb").read()
endian = "<"
i = 0
s2c = []
c2s = []
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
            proto = pd[ipoff + 9]
            sip = pd[ipoff + 12:ipoff + 16]
            dip = pd[ipoff + 16:ipoff + 20]
            if proto == 6:
                sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
                if sp == 1211 or dp == 1211:
                    seq = struct.unpack_from(">I", pd, ipoff + ihl + 4)[0]
                    doff = (pd[ipoff + ihl + 12] >> 4) * 4
                    payload = pd[ipoff + ihl + doff:]
                    if sp == 1211:
                        s2c.append((seq, payload, ipoff))
                    else:
                        c2s.append((seq, payload, ipoff))
                break
    i += bl

print(f"C2S 包 {len(c2s)}, S2C 包 {len(s2c)}")
# dump S2C 前 3 个
for seq, payload, ipoff in s2c[:3]:
    print(f"seq={seq} ipoff={ipoff} len={len(payload)} {payload[:60].hex(' ')}")

# 重组 S2C
from seer_rebuild.protocol import FrameSplitter
s2c_sorted = sorted(s2c, key=lambda x: x[0])
buf = bytearray()
prev = None
for seq, payload, _ in s2c_sorted:
    if seq == prev:
        continue
    prev = seq
    buf.extend(payload)
print(f"S2C 流 {len(buf)}B")
sp = FrameSplitter("h5")
try:
    frames = sp.push(bytes(buf))
    print(f"S2C 帧 {len(frames)}")
    for f in frames[:20]:
        print(f"  cmd={f.cmd} len={len(f.body)} body={f.body[:80].hex()}")
except Exception as e:
    print("S2C 解析失败:", e)