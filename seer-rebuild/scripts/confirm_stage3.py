"""确认当前戟决先锋所在的关卡：进因子(41284/41282)读 2503/2504 体积 + 解码 BOSS。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

ACCOUNT, PASSWORD = "ACCOUNT", "PASSWORD"


def utf8_strings(b: bytes, min_len=3):
    out = []
    cur = bytearray()
    for byte in b:
        if 0x20 <= byte < 0x7F or byte >= 0x80:
            cur.append(byte)
        else:
            if len(cur) >= min_len:
                try:
                    out.append(cur.decode("utf-8"))
                except Exception:
                    pass
            cur = bytearray()
    if len(cur) >= min_len:
        try:
            out.append(cur.decode("utf-8"))
        except Exception:
            pass
    return out


async def main():
    sess = authenticate(ACCOUNT, PASSWORD)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)

    await c.send(41284, [struct.pack(">I", 228), struct.pack(">I", 1)])
    await c.send(41282, [struct.pack(">I", 228), struct.pack(">I", 1)])

    loop = asyncio.get_running_loop()
    end = loop.time() + 8.0
    got_2503 = None
    got_2504 = None
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 2503 and got_2503 is None:
            got_2503 = f.body
        elif f.cmd == 2504 and got_2504 is None:
            got_2504 = f.body
        if got_2503 is not None and got_2504 is not None:
            break
    await c.close()

    print("=== 当前关卡识别（2503 战斗初始化 / 2504 开战）===")
    if got_2503:
        print(f"2503 len={len(got_2503)}")
        print("  UTF-8 串:", utf8_strings(got_2503))
        # 前若干 u32
        print("  头u32:", [hex(struct.unpack_from('>I', got_2503, i)[0]) for i in range(0, min(56, len(got_2503)), 4) if i + 4 <= len(got_2503)])
    else:
        print("2503 未捕获")
    if got_2504:
        print(f"2504 len={len(got_2504)}")
        print("  头u32:", [hex(struct.unpack_from('>I', got_2504, i)[0]) for i in range(0, min(56, len(got_2504)), 4) if i + 4 <= len(got_2504)])
    else:
        print("2504 未捕获")

    # 判据：单精灵关 2503~924B / 2504~442B；多精灵关 2503>2200B / 2504~567B
    if got_2503 is not None and len(got_2503) <= 1000:
        print("\n=> 判定：仍是【单精灵关 = 第3关 卡杉德拉】，第三关【尚未登记过关】")
    elif got_2503 is not None:
        print("\n=> 判定：已到【多精灵关 = 第4关 克利奥】，第三关【已通过】")


asyncio.run(main())