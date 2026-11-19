"""统一“阵容 / 装备调整 + 打因子”接口（读 + 写，默认 dry-run）。

已确认协议（有抓包证据）：
  - 读背包（正式/待命）：`pets.read_bag` → 43706
  - 2304 PET_RELEASE body = `[catch_time][flag]`：
      flag 0 = 正式放回仓库 / 1 = 加入背包 / 3 = 待命放回仓库 / 4 = 正式降待命
  - 换首发/升正式：2308 PET_DEFAULT body = `[catch_time]`
  - 更换装备：2604 CHANGE_CLOTH body = `[count][equip_id × count]`（头/目镜/腰/手/足）
  - 更换称号：3404 SETTITLE body = `[title_id]`
  - 因子关卡列表：45543 body = `[start][end]`（[0,999] / [1000,1999] 分页）
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .commands import Cmd
from .features import FeatureStep, format_steps, readable_steps, list_body, u32, stage_list_step


def read_bag(account: str, password: str, *, resolve_names: bool = True) -> dict:
    """读背包（正式/待命），返回结构化 dict，见 pets.read_bag。"""
    from .pets import read_bag as _read

    return _read(account, password, resolve_names=resolve_names)


def move_step(catch_time: int, to_bag: bool) -> FeatureStep:
    """仓库↔背包移动（2304）。"""
    flag = 1 if to_bag else 0
    return FeatureStep(
        "加入背包" if to_bag else "放回仓库",
        Cmd.PET_RELEASE,
        u32(catch_time) + u32(flag),
        True,
        "PET_RELEASE",
    )


def equip_step(equip_ids: list[int]) -> FeatureStep:
    """更换装备/装扮（2604 CHANGE_CLOTH）。"""
    return FeatureStep("更换装备", Cmd.CHANGE_CLOTH, list_body(equip_ids), True, "CHANGE_CLOTH")


def title_step(title_id: int) -> FeatureStep:
    """更换称号（3404 SETTITLE）。"""
    return FeatureStep("更换称号", Cmd.SETTITLE, u32(title_id), True, "SETTITLE")


def starter_step(catch_time: int) -> FeatureStep:
    """换首发 / 升为正式：2308 PET_DEFAULT，body=[catch_time]。"""
    return FeatureStep("设默认/换首发", Cmd.PET_DEFAULT, u32(catch_time), True, "PET_DEFAULT")


def demote_step(catch_time: int) -> FeatureStep:
    """降为待命：2304 PET_RELEASE flag=4，body=[catch_time][4]。"""
    return FeatureStep("降为待命", Cmd.PET_RELEASE, u32(catch_time) + u32(4), True, "PET_RELEASE(-4)")


def clear_reserve_step(catch_time: int) -> FeatureStep:
    """清除待命精灵（待命→仓库）：2304 PET_RELEASE flag=3，body=[catch_time][3]。

    lxy_yz.pcapng（打因子·切换精灵）实证：待命精灵用 flag=3 清出；flag=0 只对正式精灵有效。
    """
    return FeatureStep("清除待命", Cmd.PET_RELEASE, u32(catch_time) + u32(3), True, "PET_RELEASE(-3)")


def add_reserve_step(catch_time: int) -> FeatureStep:
    """加入待命：2304 PET_RELEASE flag=2，body=[catch_time][2]。

    lxy_yz_2 实证：打因子切阵容时，正式用 flag=1、待命用 flag=2。
    """
    return FeatureStep("加入待命", Cmd.PET_RELEASE, u32(catch_time) + u32(2), True, "PET_RELEASE(-2)")


def lineup_steps(*, starter: int | None = None, demote: int | None = None) -> list[FeatureStep]:
    """调整出战阵容。已实证（change_place.pcapng + S2C 43706 变化）：
      - starter：2308 PET_DEFAULT，把 catch_time 对应精灵设为默认/首发（待命→正式、或提到第 1 位）。
      - demote：2304 flag=4，把该精灵从正式降为待命。
    仓库移入/移出用 move_step()（2304 flag=1/0），清待命用 clear_reserve_step()（2304 flag=3）。
    """
    steps = []
    if starter is not None:
        steps.append(starter_step(starter))
    if demote is not None:
        steps.append(demote_step(demote))
    return steps


def factor_cycle_steps(
    *,
    equip_ids: list[int] | None = None,
    title_id: int | None = None,
    switches: list[tuple[int, int]] | None = None,
    factor_ids: list[int] | None = None,
) -> list[FeatureStep]:
    """打因子一轮：切换装备/称号/精灵 → 因子关卡列表 → 因子信息 → 进图。

    实证：lxy_yz.pcapng / factor_write_only.pcapng（雷小伊“打因子”）。
    switches 里 flag 用 2304 语义：0 放回 / 1 加入 / 3 清待命 / 4 降待命。
    """
    steps: list[FeatureStep] = []
    if equip_ids:
        steps.append(equip_step(equip_ids))
    if title_id is not None:
        steps.append(title_step(title_id))
    for catch, flag in (switches or []):
        name = {0: "放回仓库", 1: "加入背包", 3: "清除待命", 4: "降待命"}.get(flag, f"flag={flag}")
        steps.append(FeatureStep(f"切换精灵({name})", Cmd.PET_RELEASE, u32(catch) + u32(flag), True, "PET_RELEASE"))
    steps.append(stage_list_step(0, 999))
    steps.append(stage_list_step(1000, 1999))
    if factor_ids:
        steps.append(FeatureStep("因子信息", Cmd.GET_MULTI_FOREVER, list_body(factor_ids), False, "GET_MULTI_FOREVER"))
    steps.append(FeatureStep("进入因子关卡", Cmd.ENTER_MAP, b"", True, "ENTER_MAP"))
    return steps


def present(steps: list[FeatureStep], *, send: bool = False, account: str | None = None,
            password: str | None = None) -> list[str]:
    """把步骤格式化成文本（send=False 即 dry-run）。"""
    return [s for s in (readable_steps(steps, dry_run=not send))]


async def _send_steps(account: str, password: str, steps: list[FeatureStep], *, write: bool) -> list[str]:
    from .connection import open_unity

    c = await open_unity(account, password)
    out: list[str] = []
    loop = asyncio.get_running_loop()
    for s in steps:
        if s.write and not write:
            out.append(f"[dry-run] skip write {s.name} cmd={s.cmd}")
            continue
        try:
            await c.send(s.cmd, [s.body] if s.body else [])
        except (ConnectionError, asyncio.IncompleteReadError) as e:
            out.append(f"[send-failed] {s.name} cmd={s.cmd}: {e}")
            break
        out.append(f"[sent] {s.name} cmd={s.cmd} body={s.body.hex()}")
        # 关键：每步之间收 S2C，让 result 链吸收服务端 result，否则下一帧校验和错、被服务端拒绝。
        end = loop.time() + 1.2
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                break
            if f.result != 0 or f.cmd in (2304, 2308, 2604, 3404, 43706, 2001, 2002, 1002):
                out.append(f"    [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:24].hex()}")
    await c.close()
    return out


def execute(account: str, password: str, steps: list[FeatureStep], *, send: bool = False) -> list[str]:
    """统一执行入口：send=False 只打印要发的包（dry-run），send=True 才真正发写命令。"""
    if not send:
        return [f"[dry-run] {len(steps)} 步，不发送（加 --send 才真发）"] + readable_steps(steps, dry_run=True)
    return asyncio.run(_send_steps(account, password, steps, write=True))