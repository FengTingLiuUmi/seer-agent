"""解析 mizyx.pcapng 的指定 TCP 流（由 tshark follow,tcp,raw 提供重组流）。"""
import subprocess
import struct
import sys
from collections import Counter
from pathlib import Path

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"


def follow(pcap: Path, stream: int) -> tuple[bytearray, bytearray]:
    r = subprocess.run(
        [TSHARK, "-r", str(pcap), "-q", "-z", f"follow,tcp,raw,{stream}"],
        capture_output=True,
    )
    out = r.stdout.decode("utf-8", "replace")
    c2s = bytearray()
    s2c = bytearray()
    for line in out.splitlines():
        if not line.strip():
            continue
        s = line.strip()
        if s and s[0] in "=FN":
            continue
        s = s.replace(" ", "")
        try:
            b = bytes.fromhex(s)
        except Exception:
            continue
        if line.startswith("\t"):
            s2c += b
        else:
            c2s += b
    return c2s, s2c


def frames(buf: bytes, versions=(0x31, 0x3E, 0x2A, 0x00)) -> list:
    out = []
    off = 0
    while off + 17 <= len(buf):
        total = struct.unpack_from(">I", buf, off)[0]
        ver = buf[off + 4]
        if 17 <= total <= 0x800000 and ver in versions and off + total <= len(buf):
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            out.append((ver, cmd, buf[off + 17:off + total]))
            off += total
            continue
        off += 1
    return out


def main() -> None:
    pcap = Path(sys.argv[1])
    stream = int(sys.argv[2])
    c2s, s2c = follow(pcap, stream)
    fc = frames(bytes(c2s))
    fs = frames(bytes(s2c))
    print(f"stream={stream} C2S={len(fc)} {dict(Counter(c for _, c, _ in fc))}")
    print(f"stream={stream} S2C={len(fs)} {dict(Counter(c for _, c, _ in fs))}")
    print("\n=== C2S ===")
    for i, (v, c, b) in enumerate(fc, 1):
        print(f"{i:03d} v=0x{v:02x} cmd={c} len={len(b)} body={b[:48].hex()}")
    print("\n=== S2C (关键) ===")
    key = {0, 2404, 2405, 2408, 2503, 2504, 2505, 2506, 2595, 2441, 42396, 42395, 47136, 41413, 41129, 41306, 4549, 11187}
    for i, (v, c, b) in enumerate(fs, 1):
        if c in key or i <= 10:
            print(f"{i:03d} v=0x{v:02x} cmd={c} len={len(b)} body={b[:40].hex()}")


if __name__ == "__main__":
    main()