import struct

pcap = "seer-rebuild/petbag_ws.pcapng"
SERVER_PORT = 1211
d = open(pcap, "rb").read()
endian = "<"

streams = {"C2S": [], "S2C": []}
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
        for ipoff in range(0, min(len(pd) - 40, 96)):
            if len(pd) < ipoff + 40:
                break
            if pd[ipoff] >> 4 != 4:
                continue
            ihl = (pd[ipoff] & 0x0F) * 4
            proto = pd[ipoff + 9]
            if proto != 6:
                break
            sp, dp = struct.unpack_from(">HH", pd, ipoff + ihl)
            if sp != SERVER_PORT and dp != SERVER_PORT:
                break
            seq = struct.unpack_from(">I", pd, ipoff + ihl + 4)[0]
            doff = (pd[ipoff + ihl + 12] >> 4) * 4
            payload = pd[ipoff + ihl + doff:]
            if payload:
                direction = "S2C" if sp == SERVER_PORT else "C2S"
                streams[direction].append((seq, payload))
            break
    i += bl

print("C2S 包数:", len(streams["C2S"]), "S2C 包数:", len(streams["S2C"]))

from seer_rebuild.protocol import FrameSplitter

for direction in ("C2S", "S2C"):
    packs = sorted(streams[direction], key=lambda x: x[0])
    buf = bytearray()
    prev_seq = None
    for seq, payload in packs:
        if seq == prev_seq:
            continue
        prev_seq = seq
        buf.extend(payload)
    sp = FrameSplitter("h5")
    try:
        frames = sp.push(bytes(buf))
    except Exception as e:
        print(f"{direction}: 流 {len(buf)}B 解析失败 {e}")
        continue
    print(f"\n=== {direction} ({len(frames)} 帧) ===")
    for f in frames:
        if f.cmd not in (3452, 8002, 45827):
            print(f"  cmd={f.cmd} len={len(f.body)} body={f.body[:100].hex()}")