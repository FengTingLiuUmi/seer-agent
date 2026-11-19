"""压血 / 自动恢复 / 全体回复能力（Unity 明文链路）。

把指定打手送进「圣尊啸傲·白虎试炼」，白虎一发把它打到残血，再关掉「自动恢复」让
残血持久化，从而喂出「当前HP低于对手则威力翻倍/低血增伤」一类技能（如 希瓦 33301
湮灭幽袭、弑序神罗的低血翻倍技）。

命令序列已从 `seer/reverse/yaxue.pcapng` + 雷小伊工具箱「压血」流程反解，并在
「伊娜普通第4关前置」实测通过：

  41228 [u32 开关]       自动恢复开关（0x6afe0b13=关 / 0x6afe0b1e=开；抓包常量）
  47136                   治疗（空 body，实测回满全体；42036 抓包标签「回复」但不治血，弃用）
  41129 [u32 8684]       发起白虎战(8684=圣尊啸傲·白虎试炼) -> S2C 2503
  2404                   准备战斗 -> S2C 2404(seed) + 2504(开战)
  {2407[catch] + 2405[技]}*N   逐只送血（白虎在自己回合把精灵打到残血）
  （2506 战斗结束自动到来，之后不再发 2410）

注意：
  - 写操作默认 dry-run，`--send` 才真发。
  - 不要与官方客户端/雷小伊同时在线（顶号）；真机一律用小号。
"""
from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass

from .commands import Cmd

AUTO_RECOVER_OFF = 0x6AFE0B13   # 41228 body 显式值：关闭自动恢复（抓包常量）
AUTO_RECOVER_ON = 0x6AFE0B1E    # 41228 body 显式值：打开自动恢复（抓包常量）
CURE = Cmd.PET_CURE_FREE         # 治疗（空 body，实测回满全体）
BAIHU_BATTLE_ID = 8684          # 41129 发起 圣尊啸傲·白虎试炼


def _u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


@dataclass(slots=True)
class Target:
    """一只要压血的精灵个体。catch_time 是唯一个体标识。"""
    catch_time: int
    skill: int | None = None   # 2405 出招技能；None = 发送时读 2301 自动取首个装备技
    name: str = ""
    species_id: int | None = None


@dataclass(slots=True)
class Step:
    name: str
    cmd: int
    body: bytes = b""


def build_steps(targets: list[Target], *, close_auto: bool = True, recover: bool = False,
                starter: int | None = None) -> list[Step]:
    """把压血流程展开成命令步骤列表（纯函数，供 dry-run 与离线测试）。

    starter = 首发(当前在场)的 catch_time；压血目标若等于它，则跳过 2407（已在场，直接 2405，
    否则服务端 10021 拒绝换成一只已在场的精灵）。
    """
    steps: list[Step] = []
    if close_auto:
        steps.append(Step("关自动恢复", Cmd.AUTO_RECOVER_SWITCH, _u32(AUTO_RECOVER_OFF)))
    if recover:
        steps.append(Step("治疗(47136)", CURE, b""))
    steps.append(Step("发起白虎战·圣尊啸傲白虎试炼", Cmd.BAIHU_TRIAL, _u32(BAIHU_BATTLE_ID)))
    steps.append(Step("准备战斗", Cmd.READY_TO_FIGHT, b""))
    steps += list(iter_battle_steps(targets, starter=starter))
    steps.append(Step("结束战斗", Cmd.END_BATTLE, b""))
    return steps


def iter_battle_steps(targets: list[Target], *, starter: int | None = None) -> list[Step]:
    """进入战斗后的动作：不是当前在场精灵才 2407 换宠，再 2405 出招。"""
    steps: list[Step] = []
    current = starter
    for i, t in enumerate(targets, 1):
        if t.catch_time and t.catch_time != current:
            steps.append(Step(f"切换精灵 #{i} catch={t.catch_time}", Cmd.SWITCH_PET, _u32(t.catch_time)))
            current = t.catch_time
        steps.append(Step(f"出招 #{i} {t.name or t.catch_time}", Cmd.USE_SKILL, _u32(t.skill or 0)))
    return steps


def format_steps(steps: list[Step]) -> list[str]:
    lines: list[str] = []
    for s in steps:
        lines.append(f"  {s.name}  cmd={s.cmd}  body={s.body.hex() if s.body else ''}")
    return lines


def resolve_from_species(account: str, password: str, species_ids: list[int], *,
                         resolve_names: bool = True) -> tuple[list[Target], list[str]]:
    """手机的读背包，把 species_id 映射成背包里的个体 catch_time。

    同名多只全部列出（压血最好用 --catch-time 精确到个体）。找不到的物种记入 warnings。
    """
    from .pets import read_bag

    bag = read_bag(account, password, resolve_names=resolve_names)
    targets: list[Target] = []
    warnings: list[str] = []
    pools = [p for g in ("正式", "待命") for p in bag.get(g, [])]
    for sid in species_ids:
        found = [p for p in pools if p.get("species_id") == sid]
        if not found:
            warnings.append(f"species={sid} 不在当前背包，已跳过")
            continue
        for p in found:
            targets.append(Target(
                catch_time=int(p["catch_time"]),
                species_id=sid,
                name=p.get("name") or str(sid),
            ))
    return targets, warnings


def _species_name(data, species_id: int) -> str:
    sp = data.species.get(species_id) if data is not None else None
    return sp.name if sp else str(species_id)


async def _read_detail(client, catch_time: int) -> object | None:
    """在已连接会话里读个体 2301 详情（不额外登录）。"""
    from .pet_details import parse_2301

    f = await client.request(Cmd.GET_PET_INFO, [_u32(catch_time)], timeout=6.0)
    return parse_2301(f.body)


async def _send(client, cmd: int, body: bytes, out: list[str], *, wait: float = 1.0) -> None:
    await client.send(cmd, [body] if body else [])
    out.append(f"[sent] cmd={cmd} body={body.hex() if body else ''}")
    loop = asyncio.get_running_loop()
    end = loop.time() + wait
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(client.frames.get(), timeout=min(0.6, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        out.append(f"  [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:40].hex()}")


async def _send_observe(client, cmd: int, body: bytes, out: list[str], *,
                        wait: float = 1.0, stop_cmd: int | None = None) -> bool:
    """发送并收集响应；返回是否在 wait 窗口内见到 stop_cmd（用于捕捉 2506 战斗结束）。"""
    await client.send(cmd, [body] if body else [])
    out.append(f"[sent] cmd={cmd} body={body.hex() if body else ''}")
    loop = asyncio.get_running_loop()
    end = loop.time() + wait
    saw = False
    while loop.time() < end:
        try:
            f = await asyncio.wait_for(client.frames.get(), timeout=min(0.6, end - loop.time()))
        except asyncio.TimeoutError:
            continue
        if stop_cmd is not None and f.cmd == stop_cmd:
            saw = True
        out.append(f"  [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:40].hex()}")
    return saw


async def _run_async(account: str, password: str, targets: list[Target], *,
                     close_auto: bool, recover: bool, resolve_names: bool) -> list[str]:
    from .battle_data import BattleData
    from .connection import open_unity

    data = BattleData(r"F:\seer\seer_cfg\json") if resolve_names else None
    c = await open_unity(account, password)
    out: list[str] = []
    try:
        # 1) 逐只补 2301 详情：名字 + 当前血量 + 装备技能（缺 skill 时取首个）
        for t in targets:
            try:
                d = await _read_detail(c, t.catch_time)
            except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001
                out.append(f"[错误] 读 catch={t.catch_time} 的 2301 失败：{e}；跳过")
                t.skill = None
                continue
            if d.species_id and resolve_names:
                t.name = _species_name(data, d.species_id)
                t.species_id = d.species_id
            if t.skill is None:
                t.skill = d.skills[0] if d.skills else 0
            out.append(f"[2301] {t.name or t.catch_time} catch={t.catch_time} "
                       f"当前体力={d.cur_hp}/{d.max_hp} 装备技能={d.skills}")

        usable = [t for t in targets if t.catch_time and t.skill]
        skipped = [t for t in targets if not (t.catch_time and t.skill)]
        for t in skipped:
            out.append(f"[跳过] {t.name or t.catch_time}：无 catch_time 或无可用技能，不能压血")

        if not usable:
            out.append("[错误] 没有可压血的目标")
            return out

        # 2) 读首发(正式[0])，避免对已在场精灵发 2407（否则服务端 10021 拒绝）
        starter: int | None = None
        try:
            from .pets import parse_bag_43706
            f = await c.request(Cmd.GET_PET_INFO_BY_ONCE, [], timeout=6.0)
            _cnt, _pets = parse_bag_43706(f.body)
            if _pets:
                starter = _pets[0].catch_time
        except Exception as e:  # noqa: BLE001
            out.append(f"[提示] 读首发失败（{e}），按无首发处理")
        out.append(f"[首发] catch={starter}")

        # 3) 发流程
        if close_auto:
            await _send(c, Cmd.AUTO_RECOVER_SWITCH, _u32(AUTO_RECOVER_OFF), out)
            out.append("  已关闭自动恢复（压血持久化关键，别在压血前开回）")
        if recover:
            await _send(c, CURE, b"", out, wait=2.0)
        await _send(c, Cmd.BAIHU_TRIAL, _u32(BAIHU_BATTLE_ID), out, wait=2.0)
        await _send(c, Cmd.READY_TO_FIGHT, b"", out, wait=2.0)
        battle_over = False
        for s in iter_battle_steps(usable, starter=starter):
            seen = await _send_observe(c, s.cmd, s.body, out,
                                       wait=1.5 if s.cmd == Cmd.USE_SKILL else 1.0, stop_cmd=Cmd.FIGHT_OVER)
            battle_over = battle_over or seen
        if battle_over:
            out.append("[战斗已结束(2506)] 跳过 2410")
        else:
            await _send(c, Cmd.END_BATTLE, b"", out, wait=2.0)
    finally:
        await c.close()
    return out


def run(account: str, password: str, targets: list[Target], *,
        close_auto: bool = True, recover: bool = False,
        send: bool = False, resolve_names: bool = True) -> list[str]:
    """压血入口。send=False 只打印计划（dry-run），send=True 真登录并发包。"""
    if not send:
        lines = [f"[dry-run] {len(targets)} 只要压血，不发送（加 --send 才真发）"]
        for t in targets:
            sk = f"技{t.skill}" if t.skill else "读2301自动取首个装备技"
            lines.append(f"  {t.name or t.catch_time} catch_time={t.catch_time} 出招={sk}")
        lines += format_steps(build_steps(targets, close_auto=close_auto, recover=recover))
        return lines
    lines = asyncio.run(_run_async(
        account, password, targets,
        close_auto=close_auto, recover=recover, resolve_names=resolve_names,
    ))

    # 压血后回读（用新登录，避免战斗连接因 2506/断开而读不到）
    from .battle_data import BattleData
    from .pet_details import read_pet_detail
    data = BattleData(r"F:\seer\seer_cfg\json") if resolve_names else None
    for t in [t for t in targets if t.catch_time and t.skill]:
        try:
            d = read_pet_detail(account, password, t.catch_time)
            name = _species_name(data, d.species_id)
            lines.append(f"[压血后] {name or t.catch_time} catch={t.catch_time} "
                         f"当前体力={d.cur_hp}/{d.max_hp}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"[压血后] 读 catch={t.catch_time} 失败：{e}")
    return lines


async def _restore_async(account: str, password: str) -> list[str]:
    from .connection import open_unity

    c = await open_unity(account, password)
    out: list[str] = []
    try:
        await _send(c, Cmd.AUTO_RECOVER_SWITCH, _u32(AUTO_RECOVER_ON), out)
        await _send(c, CURE, b"", out, wait=2.0)
        out.append("已开回自动恢复并治疗(47136)回满")
    finally:
        await c.close()
    return out


def restore(account: str, password: str, *, send: bool = True) -> list[str]:
    """恢复：打开自动恢复 + 全体回复（压血后的还原）。send=False 只打印计划。"""
    if not send:
        return [
            "[dry-run] 恢复 = 41228(开自动恢复) + 47136(治疗)，不发送（加 --send 才真发）",
            f"  开自动恢复 cmd=41228 body={_u32(AUTO_RECOVER_ON).hex()}",
            "  治疗       cmd=47136 body=",
        ]
    return asyncio.run(_restore_async(account, password))