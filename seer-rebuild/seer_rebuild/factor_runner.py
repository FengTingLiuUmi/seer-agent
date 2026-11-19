"""精灵因子关卡（打因子）执行器。

从雷小伊抓包重建的命令时序（证据：`lxy_yz_3.pcapng` / `lxy_yz_2.pcapng` /
`factor_write_only.pcapng`）：

  选关 + 切阵容（lxy_yz_3 / lxy_yz_2 主连接）：
    43706 打开背包(GET_PET_INFO_BY_ONCE)
    2304  清待命精灵 flag=3（每只待命一只）
    45543 因子关卡列表，分页 [0,999] + [1000,1999]
    2304  加正式精灵 flag=1 / 加待命精灵 flag=2
    43706 打开背包（刷新）

  真机打一关（lxy_yz_2 主连接 1203）：
    47136 免费治疗(PET_CURE_FREE)
    42396 发起 PVE BOSS 战：body=[关卡id][1][1]
    2404  准备战斗：空
    2405  出招：body=[技能id]（可循环；S2C 2506 = 战斗结束）
    47136 免费治疗（战后回复）

  领取/进入因子（factor_write_only / features.CAPTURE_FACTOR）：
    41413 body=[factor_id][action0][action1]

写操作默认 dry-run；只有显式 ``send=True`` 才真正发包。读进度/关卡列表是只读。
"""
from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field

from .commands import Cmd
from .features import FeatureStep, list_body, u32, stage_list_step
from .factor import (
    CURRENT_FACTOR,
    FactorSpec,
    factor_progress,
    factor_enter_steps,
    load_factor_spec,
)
from .team import (
    add_reserve_step,
    clear_reserve_step,
    equip_step,
    title_step,
)
from .battle_driver import LiveBattleContextBuilder, drive_battle
from .action_policy import Action, PetInfo, ScriptedPolicy

# 命令表（值统一在 commands.Cmd 维护，这里只留可读别名）
GET_PET_INFO_BY_ONCE = Cmd.GET_PET_INFO_BY_ONCE
PET_RELEASE = Cmd.PET_RELEASE
STAGE_LIST = Cmd.STAGE_LIST
GET_MULTI_FOREVER = Cmd.GET_MULTI_FOREVER
ENTER_MAP = Cmd.ENTER_MAP
CHANGE_CLOTH = Cmd.CHANGE_CLOTH
SETTITLE = Cmd.SETTITLE
PET_CURE_FREE = Cmd.PET_CURE_FREE
FIGHT_H5_PVE_BOSS = Cmd.FIGHT_H5_PVE_BOSS
READY_TO_FIGHT = Cmd.READY_TO_FIGHT
USE_SKILL = Cmd.USE_SKILL
FIGHT_OVER = Cmd.FIGHT_OVER
FACTOR_ACTION = Cmd.FACTOR_ACTION

# 2304 PET_RELEASE 的 flag 语义（lxy_yz / lxy_yz_2 实证）
FLAG_TO_WAREHOUSE = 0          # 正式 → 仓库
FLAG_TO_BAG = 1                # 仓库 → 正式背包
FLAG_TO_RESERVE = 2            # 仓库 → 待命
FLAG_CLEAR_RESERVE = 3         # 待命 → 仓库
FLAG_DEMOTE = 4                # 正式 → 待命


# ---------------------------------------------------------------------------
# 数据解析
@dataclass(slots=True)
class StageEntry:
    """45543 关卡列表的一项（16 字节）。"""
    entry_id: int      # 关卡/species id
    timestamp: int     # 解锁时间（unix 秒）
    flag: int          # 0=普通，14=已通关标记等
    progress: int      # 进度（100=满）

    def as_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "flag": self.flag,
            "progress": self.progress,
        }


def parse_stage_list(body: bytes) -> list[StageEntry]:
    """解析 45543 响应：`[count u32] + count × 16B`。"""
    if len(body) < 4:
        return []
    count = struct.unpack_from(">I", body, 0)[0]
    out: list[StageEntry] = []
    for k in range(count):
        off = 4 + k * 16
        if off + 16 > len(body):
            break
        a, b, c, d = struct.unpack_from(">IIII", body, off)
        out.append(StageEntry(a, b, c, d))
    return out


def parse_forever(body: bytes) -> list[int]:
    """解析 46046 响应：`[count u32] + count × u32`。"""
    if len(body) < 4:
        return []
    count = struct.unpack_from(">I", body, 0)[0]
    out: list[int] = []
    for k in range(count):
        off = 4 + k * 4
        if off + 4 > len(body):
            break
        out.append(struct.unpack_from(">I", body, off)[0])
    return out


def forever_query(ids: list[int]) -> FeatureStep:
    """46046 因子信息查询（只读）。"""
    return FeatureStep("因子信息", GET_MULTI_FOREVER, list_body(ids), False, "GET_MULTI_FOREVER")


# ---------------------------------------------------------------------------
# 步骤构造
@dataclass(slots=True)
class FactorStagePlan:
    """打一关的完整参数。

    ``lineup`` / ``reserve`` 是**精灵 species**（用于技能映射与展示）；
    ``lineup_catch`` / ``reserve_catch`` 是**个体 catch_time**（用于 2304 切阵容）。
    不提供 catch_time 时跳过切阵容，只发起战斗（用当前出战阵容）。
    """
    stage_index: int
    boss_species: int | None = None
    boss_name: str = ""
    lineup: list[int] = field(default_factory=list)          # 正式精灵 species
    reserve: list[int] = field(default_factory=list)         # 待命精灵 species
    skills: dict[int, int] = field(default_factory=dict)     # species -> 技能 id（展示/兼容）
    battle_skills: list[int] = field(default_factory=list)  # 出招顺序（由主 agent 提供）：每回合技能 id
    battle_switches: list[int] = field(default_factory=list)  # 出招间切换的 catch_time（比 battle_skills 少 1）
    lineup_catch: list[int] = field(default_factory=list)    # 2304 加正式 catch_time
    reserve_catch: list[int] = field(default_factory=list)   # 2304 加待命 catch_time
    boss_id: int | None = None                               # 42396 的关卡 id
    factor_id: int | None = None                             # 41413 领取的 factor id
    design_id: int | None = None                             # 官方端进入因子的 design_id（41284/41282）
    difficulty: int = 1                                      # 41284/41282 的难度：1=简单 2=普通 3=困难
    collect_action: tuple[int, int] = (1, 0)
    equip_ids: list[int] | None = None
    title_id: int | None = None
    clear_reserve: list[int] = field(default_factory=list)   # 待清除的待命 catch_time
    enter_map: bool = True


def lineup_switch_steps(*, clear_reserve: list[int], lineup: list[int], reserve: list[int]) -> list[FeatureStep]:
    """切阵容：清待命 → 加正式 → 加待命。每个 catch_time 一条 2304。"""
    steps: list[FeatureStep] = []
    for ct in clear_reserve:
        steps.append(clear_reserve_step(ct))
    for ct in lineup:
        steps.append(FeatureStep("加入正式精灵", PET_RELEASE, u32(ct) + u32(FLAG_TO_BAG), True, "PET_RELEASE"))
    for ct in reserve:
        steps.append(add_reserve_step(ct))
    return steps


def fight_steps(*, boss_id: int | None = None, skills: list[int] | None = None) -> list[FeatureStep]:
    """一场因子关 PVE 战斗：免费治疗 → 发起战 → 准备 → 出招循环。

    ``boss_id`` 为 42396 的关卡 id（lxy_yz_2 实测 0x6f=111）；不传则只治疗不出战。
    """
    steps: list[FeatureStep] = [
        FeatureStep("免费治疗", PET_CURE_FREE, b"", False, "PET_CURE_FREE"),
    ]
    if boss_id is not None:
        steps.append(FeatureStep("发起PVE BOSS战", FIGHT_H5_PVE_BOSS, u32(boss_id) + u32(1) + u32(1), True, "FIGHT_H5_PVE_BOSS"))
    steps.append(FeatureStep("准备战斗", READY_TO_FIGHT, b"", False, "READY_TO_FIGHT"))
    for sid in skills or []:
        steps.append(FeatureStep("出招", USE_SKILL, u32(sid), True, "USE_SKILL"))
    steps.append(FeatureStep("免费治疗", PET_CURE_FREE, b"", False, "PET_CURE_FREE"))
    return steps


def collect_step(*, factor_id: int, action: tuple[int, int] = (1, 0)) -> FeatureStep:
    """领取/进入因子：41413 body=[factor_id][action0][action1]。"""
    return FeatureStep("因子领取", FACTOR_ACTION, u32(factor_id) + u32(action[0]) + u32(action[1]), True, "FACTOR_ACTION")


def build_pre_battle_steps(plan: FactorStagePlan) -> list[FeatureStep]:
    """进入战斗前的准备步骤（整容/换装/进关）。对战本身由对战层(drive_battle)负责。"""
    steps: list[FeatureStep] = []
    steps.append(FeatureStep("打开背包", GET_PET_INFO_BY_ONCE, b"", False, "GET_PET_INFO_BY_ONCE"))
    if plan.equip_ids:
        steps.append(equip_step(plan.equip_ids))
    if plan.title_id is not None:
        steps.append(title_step(plan.title_id))
    if plan.clear_reserve or plan.lineup_catch or plan.reserve_catch:
        steps += lineup_switch_steps(clear_reserve=plan.clear_reserve, lineup=plan.lineup_catch, reserve=plan.reserve_catch)
    steps.append(stage_list_step(0, 999))
    steps.append(stage_list_step(1000, 1999))
    if plan.design_id is not None:
        # 官方 Unity 端：进入因子关 + 开始战斗（难度由 plan.difficulty 指定；BOSS 由服务端按进度自动推进）
        steps += factor_enter_steps(design_id=plan.design_id, difficulty=plan.difficulty)
    elif plan.enter_map:
        # 雷小伊旧链路：进入因子界面（2001）
        steps.append(FeatureStep("进入因子关卡", ENTER_MAP, b"", True, "ENTER_MAP"))
    return steps


def build_collect_steps(plan: FactorStagePlan) -> list[FeatureStep]:
    """战斗后的结算/领取步骤。"""
    if plan.factor_id is not None:
        return [collect_step(factor_id=plan.factor_id, action=plan.collect_action)]
    return []


def battle_policy(plan: FactorStagePlan) -> ScriptedPolicy:
    """把 plan 的出招/换宠转成「操作表能力」（固定序列 ScriptedPolicy）。"""
    seq: list[Action] = []
    for i, sid in enumerate(plan.battle_skills):
        seq.append(Action(skill_id=sid))
        if plan.battle_switches and i < len(plan.battle_switches):
            seq.append(Action(switch_to=plan.battle_switches[i]))
    return ScriptedPolicy(seq)


def battle_context(plan: FactorStagePlan) -> LiveBattleContextBuilder:
    """用 plan 的正式/待命 catch 预填 team；即使为空也返回 builder，由帧自动发现首发/敌方。"""
    team = [PetInfo(species=0, name="", catch_time=ct)
            for ct in (plan.lineup_catch or []) + (plan.reserve_catch or [])]
    return LiveBattleContextBuilder(team)


# ---------------------------------------------------------------------------
# 实机执行（默认 dry-run）
def format_plan(plan: FactorStagePlan) -> str:
    skills = ",".join(f"{s}:{plan.skills[s]}" for s in plan.lineup if s in plan.skills)
    return (
        f"第{plan.stage_index}关 BOSS={plan.boss_species}({plan.boss_name or '?'}) 关卡id={plan.boss_id} "
        f"阵容={plan.lineup} 待命={plan.reserve} catch={plan.lineup_catch}/{plan.reserve_catch} "
        f"出招={skills} 因子={plan.factor_id}"
    )


async def _send_plain(client, steps: list[FeatureStep], *, write: bool,
                      log: list[str], timeline: list[dict]) -> None:
    """发送非对战的流程步骤（整容/进关/结算），逐块收帧；不做战斗专用等待。"""
    loop = asyncio.get_running_loop()
    for s in steps:
        if s.write and not write:
            log.append(f"[dry-run] skip write {s.name} cmd={s.cmd} body={s.body.hex()}")
            continue
        try:
            await client.send(s.cmd, [s.body] if s.body else [])
        except (ConnectionError, asyncio.IncompleteReadError) as e:
            log.append(f"[send-failed] {s.name} cmd={s.cmd}: {e}")
            timeline.append({"dir": "send", "cmd": s.cmd, "body": (s.body or b"").hex(), "error": str(e)})
            break
        log.append(f"[sent] {s.name} cmd={s.cmd} body={s.body.hex()[:40]}")
        timeline.append({"dir": "send", "cmd": s.cmd, "body": (s.body or b"").hex()})
        end = loop.time() + 1.2
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(client.frames.get(), timeout=min(0.5, end - loop.time()))
            except asyncio.TimeoutError:
                break
            log.append(f"  [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:32].hex()}")
            timeline.append({"dir": "recv", "cmd": f.cmd, "result": f.result, "body": f.body.hex()})


def run(
    account: str,
    password: str,
    plans: list[FactorStagePlan],
    *,
    send: bool = False,
    write: bool = False,
    turn_wait: float = 2.0,
    resolve: bool = False,
    report_dir: str | None = None,
    on_turn=None,
    records_dir: str | None = None,
) -> list[str]:
    """统一入口。send=False 只打印步骤（dry-run）；send=True 才真机执行。

    流程分层：前置(整容/进关) → 对战驱动层(drive_battle) → 结算(41413)。
    """
    if not send:
        lines = [f"[dry-run] 不发送", "计划："]
        lines += [f"  - {format_plan(p)}" for p in plans]
        for p in plans:
            lines += ["前置："] + [f"  {s.name} cmd={s.cmd} write={s.write} body={s.body.hex()[:48]}" for s in build_pre_battle_steps(p)]
            pol = battle_policy(p)
            lines += ["对战："] + ([f"  {a.label()}" for a in pol.sequence] or ["  (无出招)"])
            cs = build_collect_steps(p)
            if cs:
                lines += ["结算："] + [f"  {s.name} cmd={s.cmd} body={s.body.hex()[:48]}" for s in cs]
        return lines

    from .connection import open_unity

    async def _run() -> list[str]:
        c = await open_unity(account, password)
        lines = ["计划："] + [f"  - {format_plan(p)}" for p in plans]
        timeline: list[dict] = []
        all_turns: list[dict] = []
        import json as _json
        from pathlib import Path as _Path
        from .battle_records import DEFAULT_RECORDS_DIR, append_timeline, reset_live
        from .battle_data import BattleData as _BD

        # 技能名/精灵名反查（本地战斗库），供实时战报与 results 落盘使用。
        _bd = _BD(r"F:\seer\seer_cfg\json")
        skill_names = {sid: m.name for sid, m in _bd.moves.items()}
        species_names = {sid: s.name for sid, s in _bd.species.items()}

        # 技能名在线兜底（SeerAPI 懒加载）：本地战斗库缺的 BOSS 专属技
        # （如「临时改良/工业套组/绝境脱出」）在实时 timeline / 回合表里也要即时反查，
        # 否则前端战报会把敌方技能显示成裸 id。
        _prov = None

        def _resolve_skill(sid: int):
            nonlocal _prov
            if _prov is None:
                try:
                    from .provider import SeerApiProvider
                    _prov = SeerApiProvider()
                except Exception:
                    _prov = False
            if _prov is False:
                return None
            try:
                return _prov.name("skill", sid)
            except Exception:
                return None

        rec_dir = records_dir if records_dir is not None else str(DEFAULT_RECORDS_DIR)
        turns_fh = None
        if report_dir:
            _Path(report_dir).mkdir(parents=True, exist_ok=True)
            turns_fh = open(_Path(report_dir, "turns.jsonl"), "w", encoding="utf-8")
        if rec_dir:
            reset_live(rec_dir)

        # 阵容配置确认：装备 + 称号也是阵容的一环，打前先从 1001 快照读出来。
        try:
            from .inventory import snapshot_from_1001
            lf = getattr(c, "login_frame", None)
            if lf is not None:
                snap = snapshot_from_1001(lf.body)
                lines.append(f"[阵容·装备] ids={[e.id for e in snap.equipment]}"
                             f" 称号 ids={[t.id for t in snap.titles]}"
                             f"  (空 = 没穿有加成的装备/没戴称号，伤害会缺增伤)")
        except Exception as _e:  # noqa: BLE001
            lines.append(f"[阵容·装备] 读取失败：{_e}")

        def _on_frame(ev: dict) -> None:
            if rec_dir:
                append_timeline(ev, rec_dir)

        def _handle_turn(rec: dict) -> None:
            all_turns.append(rec)
            if turns_fh is not None:
                turns_fh.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                turns_fh.flush()
            if on_turn is not None:
                on_turn(rec)

        last_res = None
        for p in plans:
            await _send_plain(c, build_pre_battle_steps(p), write=write, log=lines, timeline=timeline)
            pol = battle_policy(p)
            if pol.sequence and write:
                res = await drive_battle(c, pol, turn_wait=turn_wait, log=lines,
                                         context=battle_context(p), on_turn=_handle_turn, on_frame=_on_frame,
                                         skill_names=skill_names, resolve_skill=_resolve_skill)
                timeline.extend(res.frames)
                last_res = res
                lines.append(f"[对战] 结束(2506)={res.over} 过关(45827)={res.passed}")
            await _send_plain(c, build_collect_steps(p), write=write, log=lines, timeline=timeline)

        # 打完后写 latest.json（含当前阵容 + 结果），前端据此做 catch->name 反查与胜负判定。
        if last_res is not None and write and rec_dir:
            try:
                from .pets import parse_bag_43706
                from .battle_report import build_report_from_timeline
                from .inventory import snapshot_from_1001
                from .battle_records import record_battle

                def _nm(pet) -> str:
                    sp = _bd.species.get(pet.species_id)
                    return sp.name if sp else str(pet.species_id)

                await c.send(Cmd.GET_PET_INFO_BY_ONCE, [])
                _bag = {"正式": [], "待命": [], "uid": c.session.uid}
                _loop = asyncio.get_running_loop()
                _end = _loop.time() + 6.0
                while _loop.time() < _end:
                    _f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
                    if _f.cmd == Cmd.GET_PET_INFO_BY_ONCE:
                        cnt, _pets = parse_bag_43706(_f.body, data=_bd)
                        _bag["正式"] = [{"species_id": p.species_id, "catch_time": p.catch_time, "name": _nm(p)} for p in _pets[:cnt]]
                        _bag["待命"] = [{"species_id": p.species_id, "catch_time": p.catch_time, "name": _nm(p)} for p in _pets[cnt:]]
                        break

                lf = getattr(c, "login_frame", None)
                _snap = snapshot_from_1001(lf.body).as_dict() if lf is not None else {"equipment": [], "titles": []}

                _rep = build_report_from_timeline(
                    timeline, bag=_bag, snap=_snap,
                    skill_names=skill_names, species_names=species_names,
                    factor_name="伊娜因子", design_id=plans[-1].design_id, stage_index=plans[-1].stage_index,
                    resolve_skill=_resolve_skill,
                )
                _rep.result.over = last_res.over
                _rep.result.passed = last_res.passed
                if not _rep.result.winner:
                    _rep.result.winner = "胜利" if last_res.passed else ("未判胜负" if last_res.over else "未结束")
                record_battle(_rep.as_dict(), rec_dir)
                lines.append("[战报] latest.json 已更新（含阵容/结果，前端据此反查精灵名）")
            except Exception as _e:  # noqa: BLE001
                lines.append(f"[战报] latest.json 生成失败：{_e}")

        if turns_fh is not None:
            turns_fh.close()
        if report_dir:
            _Path(report_dir, "timeline.jsonl").write_text(
                "\n".join(_json.dumps(e, ensure_ascii=False) for e in timeline) + "\n",
                encoding="utf-8",
            )
            lines.append(f"[recorded] {len(timeline)} 帧已落盘 {report_dir}/timeline.jsonl")
            lines.append(f"[recorded] {len(all_turns)} 回合结算已落盘 {report_dir}/turns.jsonl")
        await c.close()
        return lines

    return asyncio.run(_run())


def read_state(account: str, password: str, *, resolve: bool = True, factor_id: int | None = None) -> dict:
    """只读探测：登录 → 读因子进度(46046) + 图鉴进度(45543)。

    注意：45543 是「图鉴/收集进度」，不是因子关卡列表（见 factor.py 说明）。
    """
    from .connection import open_unity

    spec = load_factor_spec(factor_id) if factor_id is not None else CURRENT_FACTOR
    keys = spec.forever_progress_keys if spec else [0]

    async def _run() -> dict:
        c = await open_unity(account, password)
        loop = asyncio.get_running_loop()

        await c.send(GET_MULTI_FOREVER, [list_body(keys)])
        await c.send(STAGE_LIST, [u32(0) + u32(999)])
        await c.send(STAGE_LIST, [u32(1000) + u32(1999)])

        forever: list[int] = []
        pokedex: list[StageEntry] = []
        end = loop.time() + 6.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == GET_MULTI_FOREVER and not forever:
                forever = parse_forever(f.body)
            elif f.cmd == STAGE_LIST:
                pokedex += parse_stage_list(f.body)
        await c.close()

        out: dict = {
            "uid": c.session.uid,
            "factor": spec.as_dict() if spec else None,
            "progress": factor_progress(forever),
            "forever": forever,
            "pokedex_count": len(pokedex),
            "pokedex": [s.as_dict() for s in pokedex[:200]],
        }
        if resolve:
            from .provider import SeerApiProvider
            prov = SeerApiProvider()
            from .battle_data import BattleData
            local = BattleData(r"F:\seer\seer_cfg\json")
            for s in out["pokedex"]:
                local_name = local.species.get(s["entry_id"])
                s["name"] = local_name.name if local_name else ""
        return out

    return asyncio.run(_run())