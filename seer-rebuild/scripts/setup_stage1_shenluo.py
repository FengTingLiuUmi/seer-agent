"""第1关换成 弑序神罗 solo（保留西游buff+目镜+称号）。真机写。"""
import asyncio, json, os, sys, io
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
    end = loop.time() + 3.5
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
    # 移出圣灵谱尼，加入弑序神罗并设首发（西游4件保留）
    await send_step(c, move_step(0x57C55A7F, to_bag=False), log)
    await send_step(c, move_step(0x5FF913DE, to_bag=True), log)
    await send_step(c, starter_step(0x5FF913DE), log)

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
            log.append("准备后背包: " + ", ".join(f"{names.get(p.species_id,p.species_id)}(0x{p.catch_time:08X})" for p in pets[:cnt]))
            break
    await c.close()
    print("\n".join(log))


if __name__ == "__main__":
    asyncio.run(main())