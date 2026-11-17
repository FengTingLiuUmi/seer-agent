"""伊娜因子（design 266）单关实机战斗驱动 + 战报落盘。

用法：
  python factor_fight.py <account> <password> --skills 31505,19314,31253 \
      --switches 0x62ef6f18,0x5ffd1dd6 [--starter 0x62d8b735] \
      [--report-dir D:/out/battle1 --factor-name 伊娜因子 --stage 5]

流程（官方 Unity 明文链路）：
  登录(捕获1001快照=装备/称号) -> 读背包阵容 -> 读进度 -> [可选2308设首发]
  -> 41284 进关 -> 41282 开战 -> 2404 准备 -> 逐 2405 出招(+2407 换宠)
  -> 收 2506 停 -> 再读进度 -> 汇总；若给了 --report-dir 则落 time/bag/snap/report。
"""
import asyncio
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pets import parse_bag_43706
from seer_rebuild.battle_data import BattleData
from seer_rebuild.inventory import snapshot_from_1001
from seer_rebuild.provider import SeerApiProvider
from seer_rebuild.battle_report import build_report_from_timeline, report_to_text

DESIGN_ID = 266
DIFFICULTY = 1
FOREVER_KEYS = [303274, 303275, 303272]  # progress / time / fail

READY = 2404
USE_SKILL = 2405
SWITCH_PET = 2407
FIGHT_OVER = 2506
ENTER = 41284
START = 41282
GET_FOREVER = 46046
SET_DEFAULT = 2308
GET_PETS = 43706

WIN_MARKERS = {42390}
BATTLE_NOISE = {1002, 45963, 8002, 3452, 4395, 2002, 2001, 2441, 42494, 1016}
KEY_CMDS = {42390, 45827, 2506, 2503, 2504, 2505}
QUIET_CMDS = {2595, 2394}


def u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def list_body(ids: list[int]) -> bytes:
    return u32(len(ids)) + b"".join(u32(x) for x in ids)


def parse_forever(body: bytes) -> list[int]:
    if len(body) < 4:
        return []
    n = struct.unpack_from(">I", body, 0)[0]
    out = []
    for k in range(n):
        off = 4 + k * 4
        if off + 4 > len(body):
            break
        out.append(struct.unpack_from(">I", body, off)[0])
    return out


def fmt_frame(cmd: int, result: int, body: bytes) -> str:
    if cmd in KEY_CMDS or result != 0:
        return f"cmd={cmd} result={result} len={len(body)} body={body.hex()}"
    if cmd in QUIET_CMDS:
        return f"cmd={cmd} len={len(body)}"
    return f"cmd={cmd} result={result} len={len(body)}"


async def read_forever(c: GameClient, timeline: list[dict] | None = None, d: str = "c2s") -> list[int]:
    body = list_body(FOREVER_KEYS)
    await c.send(GET_FOREVER, [body])
    if timeline is not None:
        timeline.append({"dir": d, "cmd": GET_FOREVER, "body": body.hex(), "result": 0})
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if timeline is not None:
            timeline.append({"dir": "s2c", "cmd": f.cmd, "body": f.body.hex(), "result": f.result})
        if f.cmd == GET_FOREVER:
            return parse_forever(f.body)
    return []


async def read_bag(c: GameClient, timeline: list[dict] | None = None) -> dict:
    await c.send(GET_PETS, [])
    if timeline is not None:
        timeline.append({"dir": "c2s", "cmd": GET_PETS, "body": "", "result": 0})
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    data = BattleData(r"F:\seer\seer_cfg\json")
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if timeline is not None:
            timeline.append({"dir": "s2c", "cmd": f.cmd, "body": f.body.hex(), "result": f.result})
        if f.cmd == GET_PETS:
            cnt, pets = parse_bag_43706(f.body, data=data)
            formal, reserve = pets[:cnt], pets[cnt:]
            return {
                "正式": [{"species_id": p.species_id, "catch_time": p.catch_time,
                           "name": data.species[p.species_id].name if p.species_id in data.species else str(p.species_id)}
                          for p in formal],
                "待命": [{"species_id": p.species_id, "catch_time": p.catch_time,
                           "name": data.species[p.species_id].name if p.species_id in data.species else str(p.species_id)}
                          for p in reserve],
            }
    return {"正式": [], "待命": []}


async def collect_quiet(c: GameClient, seconds: float, timeline: list[dict], *, record: bool) -> list[str]:
    loop = asyncio.get_running_loop()
    end = loop.time() + seconds
    lines = []
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if record:
            timeline.append({"dir": "s2c", "cmd": f.cmd, "body": f.body.hex(), "result": f.result})
        if f.cmd in BATTLE_NOISE:
            continue
        lines.append(fmt_frame(f.cmd, f.result, f.body))
    return lines


def write_report_dir(report_dir: str | None, timeline: list[dict], bag: dict, snap: dict,
                     *, factor_name: str, stage: int | None) -> None:
    if not report_dir:
        return
    p = Path(report_dir)
    p.mkdir(parents=True, exist_ok=True)
    (p / "timeline.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in timeline) + "\n", encoding="utf-8")
    (p / "bag.json").write_text(json.dumps(bag, ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "snap.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    uid = bag.get("uid") if isinstance(bag, dict) else None
    bag2 = dict(bag) if isinstance(bag, dict) else {}
    bag2.setdefault("uid", uid)
    rep = build_report_from_timeline(
        timeline, bag=bag2, snap=snap, data_root=r"F:\seer\seer_cfg\json",
        factor_name=factor_name, design_id=DESIGN_ID, stage_index=stage, enemy_max_hp=None,
    )
    (p / "report.txt").write_text(report_to_text(rep) + "\n", encoding="utf-8")
    (p / "report.json").write_text(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[战报] 已落盘到 {p}（report.txt / report.json）")


async def main() -> None:
    args = [a for a in sys.argv[1:]]
    account, password = args[0], args[1]
    skills, switches = [], []
    starter = None
    difficulty = DIFFICULTY
    report_dir, factor_name, stage = None, "", None
    i = 2
    while i < len(args):
        if args[i] == "--skills":
            skills = [int(x, 0) for x in args[i + 1].split(",") if x.strip()]
            i += 2
        elif args[i] == "--switches":
            switches = [int(x, 0) for x in args[i + 1].split(",") if x.strip()]
            i += 2
        elif args[i] == "--starter":
            starter = int(args[i + 1], 0)
            i += 2
        elif args[i] == "--difficulty":
            difficulty = int(args[i + 1])
            i += 2
        elif args[i] == "--report-dir":
            report_dir = args[i + 1]
            i += 2
        elif args[i] == "--factor-name":
            factor_name = args[i + 1]
            i += 2
        elif args[i] == "--stage":
            stage = int(args[i + 1])
            i += 2
        else:
            i += 1

    timeline: list[dict] = []

    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    c = GameClient(sess, mode="unity")
    first = await c.connect(timeout=20.0)

    # 1001 快照 → 装备/称号/装扮（若收到）
    snap: dict = {"equipment": [], "clothes": [], "titles": []}
    if first is not None and first.cmd == 1001:
        timeline.append({"dir": "s2c", "cmd": 1001, "body": first.body.hex(), "result": first.result})
        try:
            prov = SeerApiProvider()
            snap = snapshot_from_1001(first.body, prov).as_dict()
        except Exception as e:
            print(f"[warn] 解析1001快照失败: {e}")
            snap = {"equipment": [], "clothes": [], "titles": []}

    await collect_quiet(c, 0.3, timeline, record=bool(report_dir))

    bag = await read_bag(c, timeline if report_dir else None)
    bag["uid"] = sess.uid  # type: ignore[attr-defined]

    pre = await read_forever(c, timeline if report_dir else None)
    print(f"[进度前] forever(progress,time,fail) = {pre}")

    if starter is not None:
        await c.send(SET_DEFAULT, [u32(starter)])
        if report_dir:
            timeline.append({"dir": "c2s", "cmd": SET_DEFAULT, "body": u32(starter).hex(), "result": 0})
        print(f"[sent] 2308 设首发 catch={starter} (0x{starter:08x})")
        await asyncio.sleep(1.0)

    body = u32(DESIGN_ID) + u32(difficulty)
    await c.send(ENTER, [body])
    await asyncio.sleep(1.0)
    await c.send(START, [body])
    if report_dir:
        timeline.append({"dir": "c2s", "cmd": ENTER, "body": body.hex(), "result": 0})
        timeline.append({"dir": "c2s", "cmd": START, "body": body.hex(), "result": 0})
    print(f"[sent] 41284/41282 进关+开战 design={DESIGN_ID} diff={difficulty}")
    await asyncio.sleep(1.5)

    await c.send(READY, [])
    if report_dir:
        timeline.append({"dir": "c2s", "cmd": READY, "body": "", "result": 0})
    print("[sent] 2404 准备战斗")

    # 出招循环
    for idx, sid in enumerate(skills):
        await c.send(USE_SKILL, [u32(sid)])
        if report_dir:
            timeline.append({"dir": "c2s", "cmd": USE_SKILL, "body": u32(sid).hex(), "result": 0})
        print(f"[sent] 2405 出招 skill={sid}")
        loop = asyncio.get_running_loop()
        end = loop.time() + 4.0
        battle_over = False
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if report_dir:
                timeline.append({"dir": "s2c", "cmd": f.cmd, "body": f.body.hex(), "result": f.result})
            if f.cmd in BATTLE_NOISE:
                continue
            print(f"  [recv] {fmt_frame(f.cmd, f.result, f.body)}")
            if f.cmd == FIGHT_OVER:
                battle_over = True
                break
            if f.cmd == USE_SKILL and f.result != 0:
                battle_over = True
                break
        if battle_over:
            break
        if idx < len(switches) and switches[idx] != 0:
            await c.send(SWITCH_PET, [u32(switches[idx])])
            if report_dir:
                timeline.append({"dir": "c2s", "cmd": SWITCH_PET, "body": u32(switches[idx]).hex(), "result": 0})
            print(f"[sent] 2407 换宠 catch={switches[idx]} (0x{switches[idx]:08x})")
            await asyncio.sleep(0.6)

    for line in await collect_quiet(c, 5.0, timeline, record=bool(report_dir)):
        print(f"  [tail] {line}")

    post = await read_forever(c, timeline if report_dir else None)
    print(f"[进度后] forever(progress,time,fail) = {post}")

    advanced = post and pre and (post[0] != pre[0] or post[1] != pre[1])
    print(f"[判定] 进度变化={advanced}  (pre={pre} -> post={post})")
    await c.close()

    if report_dir:
        write_report_dir(report_dir, timeline, bag, snap, factor_name=factor_name, stage=stage)


if __name__ == "__main__":
    asyncio.run(main())