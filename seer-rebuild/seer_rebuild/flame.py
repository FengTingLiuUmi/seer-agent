"""战斗火焰：读火焰状态 + 领火。

协议（getfire.pcapng + 46046 实测）：
  - 读火焰状态：46046 GET_MULTI_FOREVER 读键 [0x0b61, 0x0b62, 0x31e8, 0x31e9]
      0x0b61 = 火焰类型（6=绿、7=蓝）
      0x0b62 = 火焰到期 unix 时间戳（剩余秒 = 0x0b62 - now）
  - 领火：47348 body = [领取方式 u32][火焰 id u32][0]
      领取方式 1=VIP 每日免费 / 2=消耗友谊之星；火焰 id 6=绿 / 7=蓝。
"""
from __future__ import annotations

import asyncio
import struct
import time

from .commands import Cmd
from .connection import open_unity
from .features import list_body

FLAME_KEYS = [0x0B61, 0x0B62, 0x31E8, 0x31E9]

FLAME_NAMES = {
    6: "绿火", 7: "蓝火",
}

CLAIM_VIP_FREE = 1
CLAIM_FRIENDSHIP = 2


def _flame_type_name(t: int) -> str:
    return FLAME_NAMES.get(t, f"火焰#{t}")


async def _read_flame_async(account: str, password: str) -> dict:
    c = await open_unity(account, password)
    await c.send(Cmd.GET_MULTI_FOREVER, [list_body(FLAME_KEYS)])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    vals: list[int] = []
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if f.cmd == Cmd.GET_MULTI_FOREVER:
            n = struct.unpack_from(">I", f.body, 0)[0] if len(f.body) >= 4 else 0
            vals = [struct.unpack_from(">I", f.body, 4 + i * 4)[0]
                    for i in range(n) if 4 + (i + 1) * 4 <= len(f.body)]
            break
    await c.close()

    ftype = vals[0] if len(vals) > 0 else 0
    expire = vals[1] if len(vals) > 1 else 0
    remaining = max(0, expire - int(time.time())) if expire else 0
    return {
        "flame_type": ftype,
        "flame_name": _flame_type_name(ftype) if ftype else "无火焰",
        "expire_ts": expire,
        "remaining_seconds": remaining,
    }


def read_flame_state(account: str, password: str) -> dict:
    """只读：读当前火焰状态（类型 + 到期时间 + 剩余秒）。"""
    return asyncio.run(_read_flame_async(account, password))


async def _claim_flame_async(account: str, password: str, flame_id: int, via: int) -> dict:
    body = struct.pack(">III", via, flame_id, 0)
    c = await open_unity(account, password)
    await c.send(47348, [body])
    loop = asyncio.get_running_loop()
    end = loop.time() + 4.0
    result = None
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
        except asyncio.TimeoutError:
            break
        if f.cmd == 47348:
            result = f.result
            break
    await c.close()
    return {"flame_id": flame_id, "via": via, "result": result, "ok": result == 0}


def claim_flame(account: str, password: str, flame_id: int, via: int = CLAIM_FRIENDSHIP) -> dict:
    """领火：47348。flame_id 6=绿火 7=蓝火；via 1=VIP免费 2=友谊之星。"""
    return asyncio.run(_claim_flame_async(account, password, flame_id, via))


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "read"
    acct, pw = sys.argv[2], sys.argv[3]
    if mode == "read":
        import json
        print(json.dumps(read_flame_state(acct, pw), ensure_ascii=False))
    elif mode == "claim":
        fid = int(sys.argv[4], 0) if len(sys.argv) > 4 else 6
        import json
        print(json.dumps(claim_flame(acct, pw, fid, CLAIM_FRIENDSHIP), ensure_ascii=False))