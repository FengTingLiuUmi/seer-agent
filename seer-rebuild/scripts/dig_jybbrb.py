"""解析 jybbrb.pcapng 的 TCP 流（game 端口 1211），按 [total][ver][cmd] 帧还原 C2S/S2C 时间线。"""
import subprocess
import struct
import sys
from collections import Counter
from pathlib import Path

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
ROOT = Path(__file__).resolve().parent.parent


def follow(pcap: Path, stream: int):
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
    return bytes(c2s), bytes(s2c)


def frames(buf: bytes):
    out = []
    off = 0
    n = len(buf)
    while off < n:
        # 找 17B 头：total(u32) + ver(u8) + cmd(u32) + 8B 未知，body 从 off+17 起
        if off + 17 > n:
            break
        total = struct.unpack_from(">I", buf, off)[0]
        ver = buf[off + 4]
        if 17 <= total <= 0x200000 and off + total <= n:
            cmd = struct.unpack_from(">I", buf, off + 5)[0]
            out.append((off, ver, cmd, buf[off + 17:off + total]))
            off += total
            continue
        # 无法对齐时前进 1
        off += 1
    return out


def main():
    pcap = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "jybbrb.pcapng"
    stream = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    c2s, s2c = follow(pcap, stream)
    fc = frames(c2s)
    fs = frames(s2c)
    print(f"stream={stream}  raw C2S={len(c2s)}B S2C={len(s2c)}B")
    print(f"C2S frames={len(fc)} {dict(Counter(c for _, _, c, _ in fc))}")
    print(f"S2C frames={len(fs)} {dict(Counter(c for _, _, c, _ in fs))}")
    print("\n=== C2S 时间线 ===")
    for i, (off, v, c, b) in enumerate(fc, 1):
        print(f"{i:03d} @{off:6d} v=0x{v:02x} cmd={c:6d} len={len(b):4d} body={b[:64].hex()}")
    print("\n=== S2C 时间线 ===")
    for i, (off, v, c, b) in enumerate(fs, 1):
        print(f"{i:03d} @{off:6d} v=0x{v:02x} cmd={c:6d} len={len(b):4d} body={b[:80].hex()}")


if __name__ == "__main__":
    main()