# -*- coding: utf-8 -*-
"""只读打探大号：火焰 + 装备/称号 + 因子进度/锁定（一次登录）。"""
import asyncio, json, os, struct, sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
os.environ["PYTHONIOENCODING"] = "utf-8"

from seer_rebuild.commands import Cmd
from seer_rebuild.connection import open_unity
from seer_rebuild.features import list_body
from seer_rebuild.flame import FLAME_KEYS
from seer_rebuild.inventory import snapshot_from_1001

def vault(name):
    import subprocess
    p = subprocess.run(["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                       "dsh-credential-vault", "vaultctl.mjs"), "show", name], capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))

def parse_forever(body):
    if len(body) < 4: return []
    n = struct.unpack_from(">I", body, 0)[0]
    return [struct.unpack_from(">I", body, 4+k*4)[0] for k in range(n) if 4+(k+1)*4 <= len(body)]

async def req(c, cmd, body, timeout=8.0):
    await c.send(cmd, [body] if body else [])
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end-loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == cmd:
            return f
    return None

async def main():
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    c = await open_unity(u, s, timeout=25.0)
    import time
    # flame
    flame = parse_forever((await req(c, Cmd.GET_MULTI_FOREVER, list_body(FLAME_KEYS))).body)
    ftype = flame[0] if flame else 0
    expire = flame[1] if len(flame) > 1 else 0
    # factor progress + locked
    prog = parse_forever((await req(c, Cmd.GET_MULTI_FOREVER, list_body([303330,303331,303328]))).body)
    locked = parse_forever((await req(c, Cmd.GET_MULTI_FOREVER, list_body(list(range(303304,303328))))).body)
    # 1001 snapshot (equipment + titles)
    lf = getattr(c, "login_frame", None)
    snap = snapshot_from_1001(lf.body) if lf is not None else None
    await c.close()
    out = {
        "uid": u,
        "flame_type": ftype,
        "flame_expire_ts": expire,
        "flame_remaining_s": max(0, expire - int(time.time())) if expire else 0,
        "factor_progress_time_fail": prog,
        "locked_303304_327": locked,
        "equipment": [e.id for e in snap.equipment] if snap else [],
        "title": [t.id for t in snap.titles] if snap else [],
    }
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())