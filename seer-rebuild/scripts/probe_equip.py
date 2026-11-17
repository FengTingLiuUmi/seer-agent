"""只读：连接并捕获 1001 登录快照，打印穿戴装备/装扮/称号线索。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.inventory import _worn_sections


def u32s(b: bytes) -> None:
    vals = []
    for i in range(0, len(b) - 3, 4):
        v = struct.unpack_from(">I", b, i)[0]
        vals.append(v)
    return vals


async def main() -> None:
    account, password = sys.argv[1], sys.argv[2]
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    first = await c.connect(timeout=20.0)
    print("connect() 返回帧:", "None" if first is None else f"cmd={first.cmd} result={first.result} len={len(first.body)}")
    if first is not None and first.cmd == 1001:
        body = first.body
        path = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\1001_snapshot.bin"
        open(path, "wb").write(body)
        print("1001 body 已写入", path, "len", len(body))
        clothes, equip = _worn_sections(body)
        print("装扮 clothes ids:", [hex(x) for x in clothes])
        print("装备 equip ids:", [hex(x) for x in equip])
        # 扫描 0x13xxxx 以及附近出现的可疑 title/装备 id
        all_13 = []
        for i in range(0, len(body) - 3):
            v = struct.unpack_from(">I", body, i)[0]
            if 0x130001 <= v <= 0x13FFFF:
                all_13.append((i, v))
        print("0x13xxxx 出现次数:", len(all_13))
        for off, v in all_13[:80]:
            print(f"  @{off:#06x}: {v:#010x} ({v})")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())