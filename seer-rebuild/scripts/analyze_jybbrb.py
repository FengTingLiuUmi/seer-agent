"""深挖 jybbrb.pcapng：全帧头(uid/result)解析 + 关键帧解码。

产出：
  1) 命令表（方向 × 计数 × 已知含义）
  2) 2301 精灵详情（校验 pet_details.parse_2301）
  3) 2001 登录回执、43706/2361/45963 计数
  4) 每个 C2S/S2C 帧一行，导出 frames.jsonl 备查
"""
import json
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
ROOT = Path(__file__).resolve().parent.parent

KNOWN = {
    1001: "LOGIN", 1002: "HEARTBEAT", 1105: "SERVER_TIME", 2001: "AUTH_ACK?",
    2002: "TOKEN", 2003: "AUTH_INFO", 2101: "?", 8002: "?",
    2301: "PET_DETAIL", 2303: "WAREHOUSE_LIST", 2304: "PET_RELEASE",
    2361: "GET_LOVE_PET_LIST", 2604: "CHANGE_CLOTH", 3401: "?",
    3454: "?", 4178: "?", 40001: "?", 40006: "?", 41006: "?",
    41080: "?", 41129: "?", 41185: "?", 41228: "?", 41253: "?",
    41345: "?", 41868: "?", 41870: "?", 41884: "?", 41921: "?",
    42023: "?", 42378: "?", 42406: "?", 42457: "?", 43328: "?",
    43706: "BAG_DETAIL", 4475: "ENCYC?", 45555: "?", 45793: "?",
    45807: "?", 45824: "?", 45826: "?", 45866: "?", 45873: "?",
    45963: "PET_PUSH", 46046: "FOREVER_READ", 46160: "?",
    47309: "?", 47334: "?", 47335: "?", 47336: "?",
    47341: "?", 47342: "?", 47343: "?",
    9019: "?", 9675: "?", 9908: "?",
}


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


def parse_stream(buf: bytes):
    out = []
    off = 0
    n = len(buf)
    while off + 17 <= n:
        total, ver, cmd, uid, result = struct.unpack_from(">IBIII", buf, off)
        if 17 <= total <= 0x800000 and off + total <= n:
            out.append({
                "off": off, "ver": ver, "cmd": cmd, "uid": uid,
                "result": result, "body": buf[off + 17:off + total],
            })
            off += total
            continue
        off += 1
    return out


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0] if len(b) >= o + 4 else 0


def dec_utf8(b):
    return b.split(b"\x00", 1)[0].decode("utf-8", "replace")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pcap = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "jybbrb.pcapng"
    stream = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    c2s, s2c = follow(pcap, stream)
    fc = parse_stream(c2s)
    fs = parse_stream(s2c)

    print(f"### {pcap.name} stream={stream}  C2S={len(fc)} S2C={len(fs)}")

    # 1) 命令表
    tab = defaultdict(lambda: {"c2s": 0, "s2c": 0})
    for f in fc:
        tab[f["cmd"]]["c2s"] += 1
    for f in fs:
        tab[f["cmd"]]["s2c"] += 1
    print("\n== 命令表 ==")
    for cmd in sorted(tab):
        c = tab[cmd]
        print(f"  {cmd:6d} {KNOWN.get(cmd, ''):16s} C2S={c['c2s']:3d} S2C={c['s2c']:3d}")

    # 2) 2001 登录回执
    print("\n== 2001 ==")
    for f in fs:
        if f["cmd"] == 2001:
            b = f["body"]
            lead = b[:8].hex()
            tail = b
            name = dec_utf8(b[20:64]) if len(b) > 20 else ""
            print(f"  uid={f['uid']} result={f['result']} len={len(b)} lead={lead} name~={name!r}")

    # 3) 2301 精灵详情
    print("\n== 2301 精灵详情 (S2C) ==")
    for f in fs:
        if f["cmd"] == 2301:
            b = f["body"]
            skills = [u32(b, 0x6c + i * 8) for i in range(5) if u32(b, 0x6c + i * 8)]
            print(
                f"  species={u32(b,0x00):6d} lv={u32(b,0x24):3d} "
                f"HP={u32(b,0x34)}/{u32(b,0x38)} 攻={u32(b,0x3c)} 防={u32(b,0x40)} "
                f"特攻={u32(b,0x44)} 特防={u32(b,0x48)} 速={u32(b,0x4c)} skills={skills}"
            )

    # 4) 43706 背包 / 2361 精英收藏 / 45963 背包推送
    print("\n== 43706 背包 ==")
    for f in fs:
        if f["cmd"] == 43706:
            print(f"  count={u32(f['body'], 0)} len={len(f['body'])}")
    print("== 2361 精英收藏 ==")
    for f in fs:
        if f["cmd"] == 2361:
            print(f"  count={u32(f['body'], 0)} len={len(f['body'])}")
    print("== 45963 背包推送 ==")
    for f in fs:
        if f["cmd"] == 45963:
            b = f["body"]
            c = u32(b, 0)
            name = ""
            if 0 < c < 64 and len(b) > 12:
                name = dec_utf8(b[12:80])
            print(f"  count={c} len={len(b)} name~={name!r}")

    # 5) 46046 forever 读取键
    print("\n== 46046 forever 键 (C2S) ==")
    for f in fc:
        if f["cmd"] == 46046:
            b = f["body"]
            n = u32(b, 0)
            keys = [hex(u32(b, 4 + i * 4)) for i in range(min(n, 60))]
            print(f"  n={n} keys={keys}")

    # 6) 导出 frames.jsonl
    out = ROOT / "jybbrb_frames.jsonl"
    rows = []
    for d, f in [("c2s", f) for f in fc] + [("s2c", f) for f in fs]:
        rows.append({
            "dir": d, "off": f["off"], "ver": f["ver"], "cmd": f["cmd"],
            "uid": f["uid"], "result": f["result"],
            "bodyHex": f["body"].hex(),
        })
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    print(f"\n已导出 {len(rows)} 帧 → {out}")


if __name__ == "__main__":
    main()