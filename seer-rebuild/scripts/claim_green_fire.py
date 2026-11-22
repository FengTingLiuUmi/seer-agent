# -*- coding: utf-8 -*-
"""单连接：领绿火(47348) + 读火焰状态(46046)。"""
import asyncio, json, os, struct, sys, time
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
os.environ["PYTHONIOENCODING"] = "utf-8"
from seer_rebuild.connection import open_unity
from seer_rebuild.commands import Cmd
from seer_rebuild.flame import FLAME_KEYS
from seer_rebuild.features import list_body

def vault(name):
    import subprocess
    p = subprocess.run(["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                       "dsh-credential-vault", "vaultctl.mjs"), "show", name], capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))

def parse_forever(body):
    if len(body) < 4: return []
    n = struct.unpack_from(">I", body, 0)[0]
    return [struct.unpack_from(">I", body, 4+k*4)[0] for k in range(n) if 4+(k+1)*4 <= len(body)]

async def collect(c, cmd, timeout):
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

    # 1) 领绿火
    await c.send(47348, [struct.pack(">III", 2, 6, 0)])
    f1 = await collect(c, 47348, 6.0)
    claim = {"cmd": f1.cmd, "result": f1.result, "ok": f1.result == 0} if f1 else {"none": True}

    # 2) 读火焰
    await c.send(Cmd.GET_MULTI_FOREVER, [list_body(FLAME_KEYS)])
    f2 = await collect(c, Cmd.GET_MULTI_FOREVER, 6.0)
    flame = parse_forever(f2.body) if f2 else []
    await c.close()
    ftype = flame[0] if flame else 0
    expire = flame[1] if len(flame) > 1 else 0
    print(json.dumps({"claim": claim, "flame_type": ftype,
                      "flame_remaining_s": max(0, expire - int(time.time())) if expire else 0},
                     ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())