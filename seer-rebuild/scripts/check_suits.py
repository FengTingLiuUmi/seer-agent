"""只读：用 42399 批量探测候选套装件是否已拥有。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway

CANDIDATES = {
    "银翼(已穿,对照)": [1300670, 1300671, 1300672, 1300673],
    "皇帝战铠377": [1300724, 1300725, 1300726, 1300727],
    "天启389": [1300778, 1300779, 1300780, 1300781],
    "天尊400": [1300826, 1300827, 1300828, 1300829],
    "元神守护411": [1300875, 1300876, 1300877, 1300878],
    "遗迹守护458": [1301083, 1301084, 1301085, 1301086],
}


async def main() -> None:
    account, password = sys.argv[1], sys.argv[2]
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    all_ids, labels = [], []
    for label, ids in CANDIDATES.items():
        for i in ids:
            all_ids.append(i)
            labels.append((i, label))
    body = struct.pack(">I", len(all_ids)) + b"".join(struct.pack(">I", i) for i in all_ids)
    await c.send(42399, [body])
    print(f"[sent] 42399 探测 {len(all_ids)} 件")
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 42399:
            b = f.body
            print(f"[recv] 42399 len={len(b)} body={b.hex()}")
            # 尝试两种解读：返回拥有数量 / 返回拥有标记
            u = [struct.unpack_from('>I', b, o)[0] for o in range(0, len(b)-3, 4)]
            print("u32:", u)
            break
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())