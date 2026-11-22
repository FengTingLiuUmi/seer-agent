"""一次性只读打探大号：瓦坎因子进度+锁定键 + 背包(43706) + 精英仓库(2361) + 普通仓库(2303)。"""
import asyncio, json, os, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PYTHONIOENCODING"] = "utf-8"

from seer_rebuild.commands import Cmd
from seer_rebuild.connection import open_unity
from seer_rebuild.features import list_body


def vault(name):
    import subprocess
    p = subprocess.run(
        ["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                              "dsh-credential-vault", "vaultctl.mjs"), "show", name],
        capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))


async def req_body(c, cmd, body, timeout=8.0):
    await c.send(cmd, [body] if body else [])
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == cmd:
            return f.body
    return b""


def parse_forever(body):
    if len(body) < 4:
        return []
    n = struct.unpack_from(">I", body, 0)[0]
    return [struct.unpack_from(">I", body, 4 + k * 4)[0] for k in range(n)]


def parse_43706(body):
    # [count u32] + 每只详情：species@块首，catch_time@species+0x94
    if len(body) < 4:
        return 0, []
    cnt = struct.unpack_from(">I", body, 0)[0]
    span = 0x94
    out, seen = [], set()
    for off in range(0, len(body) - span - 4):
        sp = struct.unpack_from(">I", body, off)[0]
        if not (1 <= sp <= 6000):
            continue
        if body[off + 4:off + 12] != b"\x00" * 8:
            continue
        ct = struct.unpack_from(">I", body, off + span)[0]
        if not (0x54A00000 <= ct <= 0x6C000000):
            continue
        if ct in seen:
            continue
        seen.add(ct)
        out.append({"species_id": sp, "catch_time": ct})
    return cnt, out


def parse_2361(body):
    if len(body) < 4:
        return []
    n = struct.unpack_from(">I", body, 0)[0]
    out = []
    for k in range(n):
        off = 4 + k * 12
        if off + 12 > len(body):
            break
        sp, fl, ct = struct.unpack_from(">III", body, off)
        if 1 <= sp <= 6000:
            out.append({"species_id": sp, "flag": fl, "catch_time": ct})
    return out


def parse_2303(body):
    if len(body) < 4:
        return []
    n = struct.unpack_from(">I", body, 0)[0]
    out = []
    for k in range(n):
        off = 4 + k * 16
        if off + 16 > len(body):
            break
        sp, fl, ct, lv = struct.unpack_from(">IIII", body, off)
        if 1 <= sp <= 6000:
            out.append({"species_id": sp, "flag": fl, "catch_time": ct, "level": lv})
    return out


async def main():
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    c = await open_unity(u, s, timeout=25.0)

    # 瓦坎 progress/time/fail
    forever = parse_forever(await req_body(c, Cmd.GET_MULTI_FOREVER,
                                           list_body([303330, 303331, 303328])))
    # 不可重复上阵锁定键 303304..303327
    locked_raw = parse_forever(await req_body(c, Cmd.GET_MULTI_FOREVER,
                                              list_body(list(range(303304, 303328)))))

    cnt, bag = parse_43706(await req_body(c, Cmd.GET_PET_INFO_BY_ONCE, b""))
    elite = parse_2361(await req_body(c, Cmd.GET_LOVE_PET_LIST, b""))

    normal = []
    for off in (0, 1000, 2000, 3000):
        body = await req_body(c, Cmd.GET_PET_LIST, struct.pack(">II", off, 1000))
        rows = parse_2303(body)
        normal.extend(rows)
        if len(rows) < 1000:
            break

    await c.close()

    out = {
        "uid": u,
        "vakan_forever_progress_time_fail": forever,
        "vakan_locked_slots_303304_327": locked_raw,
        "bag_count": cnt,
        "bag": bag,
        "elite_count": len(elite),
        "elite": elite,
        "normal_count": len(normal),
        "normal": normal,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())