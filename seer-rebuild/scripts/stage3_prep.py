"""查戟决先锋进度 + 弑序神罗(4169)虚空招 + 卡杉德拉(3599)技能类型。"""
import asyncio
import struct
import sys

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
from seer_rebuild.provider import SeerApiProvider
from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.factor_runner import parse_forever

p = SeerApiProvider()


def combo(cid):
    d = p.get("element_type_combination", cid)
    return (d or {}).get("name") or str(cid)


def sk(sid):
    d = p.get("skill", sid, fields=["id", "name", "power", "category", "type", "priority"])
    if not d:
        return f"{sid}:???"
    t = (d.get("type") or {}).get("id")
    return f"{sid} {d.get('name')} power={d.get('power')} 类型={combo(t) if t else '?'} 先制={d.get('priority')}"


print("=== 弑序神罗 4169 装备技能 ===")
for s in [27453, 27454, 34807, 34812]:
    print(" ", sk(s))

print("\n=== 卡杉德拉 3599 技能(前12) ===")
d = p.get("pet", 3599, fields=["id", "name", "skill", "base_stats"])
for skd in (d.get("skill") or [])[:12]:
    sid = (skd.get("skill") or {}).get("id")
    if sid:
        print("  boss:", sk(sid))


async def progress():
    sess = authenticate("ACCOUNT", "PASSWORD")
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    await c.connect(timeout=20.0)
    keys = [302210, 302211, 302208]
    await c.send(46046, [struct.pack(">I", 3) + b"".join(struct.pack(">I", k) for k in keys)])
    loop = asyncio.get_running_loop()
    end = loop.time() + 5.0
    fv = None
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == 46046 and len(f.body) >= 4:
            fv = parse_forever(f.body)
            break
    await c.close()
    print(f"\n=== 戟决先锋 46046 progress/time/fail = {fv} (第1关=0? 已过两关应=2) ===")


asyncio.run(progress())