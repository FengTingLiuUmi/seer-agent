"""聚焦：从 2361(精英仓库) 挑选精灵 → 2304 加入背包 的语义确认。

解码 jybbrb.pcapng stream 0：
  - 2361 精英收藏列表（catch_time → species_id）
  - 2304 C2S（[catch_time][flag]）
  - 43706 背包（正式/待命拆分）前后变化
"""
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
ROOT = Path(__file__).resolve().parent.parent


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
            out.append({"cmd": cmd, "body": buf[off + 17:off + total]})
            off += total
            continue
        off += 1
    return out


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0] if len(b) >= o + 4 else 0


def is_catch(v):
    return 0x54000000 <= v <= 0x6C000000


def parse_2361(body):
    """[count] + N×[species][flag][catch_time]"""
    c = u32(body, 0)
    rows = []
    for i in range(c):
        o = 4 + i * 12
        if o + 12 > len(body):
            break
        s, f, ct = u32(body, o), u32(body, o + 4), u32(body, o + 8)
        rows.append((s, f, ct))
    return c, rows


def parse_43706(body):
    """[count] + 每只[species + 148B + catch_time]。返回 count + pets。"""
    c = u32(body, 0)
    pets = []
    seen = set()
    span = 0x94
    for off in range(len(body) - span - 4):
        s = u32(body, off)
        if not (1 <= s <= 6000):
            continue
        if body[off + 4:off + 12] != b"\x00" * 8:
            continue
        ct = u32(body, off + span)
        if not is_catch(ct) or ct in seen:
            continue
        seen.add(ct)
        pets.append((s, ct))
    return c, pets


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pcap = ROOT / "jybbrb.pcapng"
    c2s, s2c = follow(pcap, 0)
    fc, fs = parse(c2s), parse(s2c)

    print("== 2361 精英收藏 ==")
    elite = {}
    for f in fs:
        if f["cmd"] == 2361:
            c, rows = parse_2361(f["body"])
            for s, fl, ct in rows:
                elite[ct] = (s, fl)
            print(f"  count={c} 解析={len(rows)}")
            # 打印 flag 分布
            flcnt = defaultdict(int)
            for _, fl, _ in rows:
                flcnt[fl] += 1
            print(f"  flag 分布={dict(flcnt)}")
            # 打印前 8 只
            for s, fl, ct in rows[:8]:
                print(f"    species={s} flag={fl} catch={ct:#x}")

    print("\n== 2304 C2S (移动) 涉及的精灵 ==")
    moved = []
    for f in fc:
        if f["cmd"] == 2304:
            ct, flag = u32(f["body"], 0), u32(f["body"], 4)
            moved.append((ct, flag))
            sp = elite.get(ct, (None, None))[0]
            print(f"  2304 catch={ct:#x} flag={flag}  species(2361)={sp}")

    print("\n== 43706 背包 (按出现顺序) ==")
    for f in fs:
        if f["cmd"] == 43706:
            c, pets = parse_43706(f["body"])
            print(f"  count={c} 识别到={len(pets)} -> {[hex(ct) for _, ct in pets]}")

    print("\n== 2304 S2C 回执 (前 48B) ==")
    for f in fs:
        if f["cmd"] == 2304:
            print(f"  len={len(f['body'])} body={f['body'][:48].hex()}")


if __name__ == "__main__":
    main()