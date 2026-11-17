"""解析 unity_yz_battle.pcapng stream 31 的战斗节奏：C2S 出招 vs S2C 回合信号。

只关心战斗帧：2404/2405(出招) 与 2408/2441/2503/2504/2505/2506/2595/41129/42390/41284/41282。
输出：S2C 按出现顺序列出战斗帧（含 2504/2505 次数），C2S 列出 2405 顺序，用于推断「每回合发招前等哪个 S2C」。
"""
import struct
import subprocess
import sys
from pathlib import Path

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
ROOT = Path(__file__).resolve().parent.parent

BATTLE = {2404, 2405, 2408, 2441, 2503, 2504, 2505, 2506, 2595, 41129, 42390, 41284, 41282, 2407, 2450, 2451, 2452}


def follow(pcap, stream):
    r = subprocess.run([TSHARK, "-r", str(pcap), "-q", "-z", f"follow,tcp,raw,{stream}"], capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    c2s, s2c = bytearray(), bytearray()
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


def parse(buf):
    out = []
    off = 0
    while off + 17 <= len(buf):
        total, ver, cmd, uid, result = struct.unpack_from(">IBIII", buf, off)
        if 17 <= total <= 0x800000 and off + total <= len(buf):
            out.append((cmd, result, buf[off + 17:off + total]))
            off += total
            continue
        off += 1
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pcap = ROOT / "unity_yz_battle.pcapng"
    c2s, s2c = follow(pcap, 31)
    fc = parse(c2s)
    fs = parse(s2c)

    print("== C2S 战斗帧顺序 ==")
    for i, (cmd, res, b) in enumerate(fc, 1):
        if cmd in BATTLE:
            print(f"  C2S #{i:03d} cmd={cmd} result={res} len={len(b)} body={b[:40].hex()}")

    print("\n== S2C 战斗帧顺序 ==")
    for i, (cmd, res, b) in enumerate(fs, 1):
        if cmd in BATTLE:
            hint = ""
            if cmd == 2504:
                hint = f" 2504-回合开启"
            elif cmd == 2505:
                hint = " 2505-技能结算"
            elif cmd == 2503:
                hint = " 2503-战斗初始化"
            print(f"  S2C #{i:03d} cmd={cmd} result={res} len={len(b)}{hint} body={b[:40].hex()}")


if __name__ == "__main__":
    main()