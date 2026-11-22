"""第1关：换成 圣灵谱尼 solo 阵容（真机写）并读回确认。"""
import asyncio, json, os, struct, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PYTHONIOENCODING"] = "utf-8"

from seer_rebuild.connection import open_unity
from seer_rebuild.team import move_step, starter_step
from seer_rebuild.commands import Cmd
from seer_rebuild.pets import parse_bag_43706


def vault(name):
    import subprocess
    p = subprocess.run(["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                                             "dsh-credential-vault", "vaultctl.mjs"), "show", name],
                       capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))


async def send_step(c, step, log):
    loop = asyncio.get_running_loop()
    try:
        await c.send(step.cmd, [step.body] if step.body else [])
    except Exception as e:
        log.append(f"[ERR] {step.name}: {e}")
        return False
    log.append(f"[sent] {step.name} cmd={step.cmd} body={step.body.hex()}")
    end = loop.time() + 3.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if f.cmd == step.cmd:
            log.append(f"  [recv] cmd={f.cmd} result={f.result} body={f.body[:16].hex()}")
            return f.result == 0
    log.append(f"  (无 {step.cmd} 回包)")
    return False


async def read_bag_async(c):
    await c.send(Cmd.GET_PET_INFO_BY_ONCE, [])
    loop = asyncio.get_running_loop()
    end = loop.time() + 6.0
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=0.8)
        except asyncio.TimeoutError:
            continue
        if f.cmd == Cmd.GET_PET_INFO_BY_ONCE:
            cnt, pets = parse_bag_43706(f.body)
            return cnt, pets


async def main():
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    names = {}
    try:
        from seer_rebuild.battle_data import BattleData
        bd = BattleData(r"F:\seer\seer_cfg\json")
        names = {sp: sp_.name for sp, sp_ in bd.species.items()}
    except Exception:
        pass

    c = await open_unity(u, s, timeout=25.0)
    log = []

    cnt, pets = await read_bag_async(c)
    log.append(f"开打前背包: 正式count={cnt} -> " + ", ".join(f"{names.get(p.species_id,p.species_id)}(0x{p.catch_time:08X})" for p in pets))

    # 把当前正式里所有非圣灵谱尼的个体放回仓库
    to_remove = [p for p in pets if p.species_id != 5000]
    for p in to_remove:
        await send_step(c, move_step(p.catch_time, to_bag=False), log)
    # 加圣灵谱尼 + 设首发
    await send_step(c, move_step(0x57C55A7F, to_bag=True), log)
    await send_step(c, starter_step(0x57C55A7F), log)

    cnt2, pets2 = await read_bag_async(c)
    log.append(f"准备后背包: 正式count={cnt2} -> " + ", ".join(f"{names.get(p.species_id,p.species_id)}(0x{p.catch_time:08X})" for p in pets2))
    await c.close()
    print("\n".join(log))


if __name__ == "__main__":
    asyncio.run(main())