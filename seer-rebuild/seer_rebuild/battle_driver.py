"""对战驱动层（赛尔号底层能力）：对一个已连接的 Unity 客户端，驱动一场对战。

职责边界：
  - 只负责「进战斗之后」的 2404 准备 + 逐回合「回合开始 → decide → 执行 → 结算」。
  - 不负责「从哪进战斗」（因子 41284/41282、压血 41129、野怪 2408 各自负责）。
  - 不负责本地模拟。
  - 「出招决策」来自独立的能力层 action_policy（操作表能力），可升级为大模型驱动。
"""
from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field
from typing import Any

from .action_policy import Action, ActionPolicy, BattleContext, PetInfo, SkillInfo
from .battle_report import (
    _EFFECT_NAMES,
    _discover_enemy,
    _enemy_action_by_eid,
    _enemy_head_block,
    _enemy_hp_from_body,
    _format_status_effects,
    _load_status_names,
    _my_action_by_catch,
    _my_hp_from_body,
    _read_action_extras,
    _settle_records,
    _team_max_hp_from_2504,
)
from .commands import Cmd

FACTOR_PASS = 45827  # 因子过关推送（单精灵关等）
FACTOR_WIN = 42390   # 战斗结束（胜利/战败都会发，不代表过关）


@dataclass(slots=True)
class BattleResult:
    """一场对战的驱动结果。"""
    over: bool = False                   # 是否收到 2506（战斗结束）
    passed: bool = False                 # 是否收到 45827（因子过关）
    frames: list[dict] = field(default_factory=list)  # timeline 帧 {'dir','cmd','result','body'}
    turns: list[dict] = field(default_factory=list)   # 每回合实时结算记录


def _u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def _default_ctx(turn: int, active_catch: int | None) -> BattleContext:
    """最小区间上下文：只含回合号与当前在场 catch。"""
    return BattleContext(
        turn=turn,
        active=PetInfo(species=0, name="", catch_time=active_catch),
        bench=[],
    )


def _parse_switch_ack(body: bytes) -> dict | None:
    """解析 2407 换宠回包：换入精灵的 species/catch/当前血/满血/技能+PP/flag。

    实测布局（换入六界神王，len=317）：
      [0x04] species  [0x08] catch  [0x1c] flag  [0x20] 当前血  [0x24] 满血
      [0x28] 技能数  [0x2c + 8i] 技能id  [0x30 + 8i] PP
    """
    if len(body) < 0x20:
        return None

    def u(off: int) -> int | None:
        return struct.unpack_from(">I", body, off)[0] if len(body) >= off + 4 else None

    species, catch = u(0x04), u(0x08)
    flag = u(0x1C)
    cur_hp, max_hp = u(0x20), u(0x24)
    n = u(0x28) or 0
    skills: list[tuple[int, int]] = []
    off = 0x2C
    for _ in range(min(n, 16)):
        if off + 8 > len(body):
            break
        sid, pp = u(off), u(off + 4)
        if sid:
            skills.append((sid, pp if pp is not None else 0))
        off += 8
    return {"species": species, "catch": catch, "flag": flag,
            "hp": cur_hp, "max_hp": max_hp, "skills": skills}


def _parse_2504(body: bytes) -> dict | None:
    """解析 2504 开战帧的首发：species@0x0c, catch@0x20, cur@0x24, max@0x28。"""
    if len(body) < 0x2C:
        return None

    def u(off: int) -> int | None:
        return struct.unpack_from(">I", body, off)[0] if len(body) >= off + 4 else None

    species, catch = u(0x0C), u(0x20)
    cur_hp, max_hp = u(0x24), u(0x28)
    return {"species": species, "catch": catch, "hp": cur_hp, "max_hp": max_hp}


class LiveBattleContextBuilder:
    """按真实 S2C 帧构建「回合开始」上下文。

    - 我方「当前血/满血」：从 2504/2505 解析；满血也可由 team 预先带入。
    - 可换精灵：team 里 catch != 当前在场的个体（血量实时更新）。
    - 敌方：满血从 2504 自动发现（或构造时传入），当前血从 2505 解析。
    - 技能/PP：换宠的 2407 回包自带换入精灵的 species/技能/PP，feed 时会实时回填。
    """
    def __init__(self, team: list[PetInfo] | None = None, *, enemy_max_hp: int | None = None):
        self.team: dict[int, PetInfo] = {
            p.catch_time: p for p in (team or []) if getattr(p, "catch_time", None) is not None
        }
        self.enemy_max_hp = enemy_max_hp
        self.my_hp: dict[int, int] = {}
        self.my_max: dict[int, int] = {ct: p.max_hp for ct, p in self.team.items() if p.max_hp}
        self.enemy_hp: int | None = None
        self.enemy_eid: int | None = None
        self.enemy_skill_id: int | None = None   # 敌方最近一结算回合使用的技能/被动
        self.last_switch_flag: int | None = None
        self.switch_kind: str | None = None   # 最近一次换宠：passive(死亡免费) / active(主动占回合)
        self.starter_catch: int | None = None

    def feed(self, f) -> None:
        cmd = f.cmd
        body = f.body or b""
        if cmd == Cmd.NOTE_START_FIGHT:          # 2504 开战
            m = _team_max_hp_from_2504(body, set(self.team))
            if m:
                self.my_max.update(m)
            info = _parse_2504(body)             # 自动发现首发
            if info and info["catch"] is not None:
                ct = info["catch"]
                p = self.team.setdefault(ct, PetInfo(species=info["species"] or 0, catch_time=ct))
                p.species = info["species"] or p.species or 0
                p.hp = info["hp"] if info["hp"] is not None else p.hp
                p.max_hp = info["max_hp"] if info["max_hp"] else p.max_hp
                if info["hp"] is not None:
                    self.my_hp[ct] = info["hp"]
                if info["max_hp"]:
                    self.my_max[ct] = info["max_hp"]
                self.starter_catch = ct
            if self.enemy_max_hp is None:
                _eid, emax = _discover_enemy([{"cmd": 2504, "body": body.hex()}], set(self.team))
                if emax:
                    self.enemy_max_hp = emax
                    self.enemy_hp = emax       # 敌方开战满血
                    self.enemy_eid = _eid
        elif cmd == Cmd.NOTE_USE_SKILL:          # 2505 结算：动作块级解析（敌方技能/血 + 我方血）
            en = _enemy_action_by_eid(body, self.enemy_eid, self.enemy_max_hp)
            if en is None:
                en = _enemy_head_block(body, set(self.team))
            if en is None:
                for r in _settle_records(body, my_catches=set(self.team)):
                    if r["role"] == "enemy":
                        en = r
                        break
            if en is not None:
                self.enemy_eid = en["id"]
                self.enemy_max_hp = en["max_hp"]
                self.enemy_hp = en["hp"]
                self.enemy_skill_id = en["skill_id"]
            for r in _settle_records(body, my_catches=set(self.team)):
                if r["role"] != "my" or r["id"] not in self.team:
                    continue
                ct = r["id"]
                if r["hp"] is not None:
                    self.my_hp[ct] = r["hp"]
                if r["max_hp"]:
                    self.my_max[ct] = r["max_hp"]
                p = self.team.get(ct)
                if p is not None:
                    if r["hp"] is not None:
                        p.hp = r["hp"]
                    if r["max_hp"]:
                        p.max_hp = r["max_hp"]
            # 我方阵亡时动作块 max 塌成 0，_settle_records 会漏掉它；用动作块级解析补记 0 血，
            # 这样驱动层的「我方受到伤害」才能正确算出（满血 → 0 的整血重伤）。
            for ct in self.team:
                ma = _my_action_by_catch(body, ct, None, self.my_max.get(ct))
                if ma is None:
                    continue
                if ma["hp"] is not None:
                    self.my_hp[ct] = ma["hp"]
                if ma["max_hp"]:
                    self.my_max[ct] = ma["max_hp"]
                p = self.team.get(ct)
                if p is not None and ma["hp"] is not None:
                    p.hp = ma["hp"]
        elif cmd == Cmd.SWITCH_PET:          # 2407 换宠回包：带回换入精灵完整状态
            info = _parse_switch_ack(body)
            if not info or info["catch"] is None:
                return
            ct = info["catch"]
            p = self.team.setdefault(ct, PetInfo(species=info["species"] or 0, catch_time=ct))
            p.species = info["species"] or p.species or 0
            p.hp = info["hp"] if info["hp"] is not None else p.hp
            p.max_hp = info["max_hp"] if info["max_hp"] else p.max_hp
            p.skills = [SkillInfo(id=sid, pp=pp) for sid, pp in info["skills"]]
            if info["hp"] is not None:
                self.my_hp[ct] = info["hp"]
            if info["max_hp"]:
                self.my_max[ct] = info["max_hp"]
            self.last_switch_flag = info["flag"]

    def build(self, turn: int, active_catch: int | None) -> BattleContext:
        active = self._pet(active_catch)
        bench = [self._pet(ct) for ct in self.team if ct != active_catch]
        enemy_known = self.enemy_hp is not None or self.enemy_max_hp is not None
        return BattleContext(
            turn=turn,
            active=active,
            bench=bench,
            enemy=PetInfo(species=0, name="敌方", hp=self.enemy_hp, max_hp=self.enemy_max_hp) if enemy_known else None,
            round_info={
                "my_hp": dict(self.my_hp),
                "my_max": dict(self.my_max),
                "enemy_hp": self.enemy_hp,
                "enemy_max_hp": self.enemy_max_hp,
                "enemy_eid": self.enemy_eid,
                "enemy_skill_id": self.enemy_skill_id,
                "last_switch_flag": self.last_switch_flag,
                "switch_kind": self.switch_kind,
            },
        )

    def _pet(self, ct: int | None) -> PetInfo:
        base = self.team.get(ct)
        if base is None:
            return PetInfo(species=0, name="", catch_time=ct)
        return PetInfo(
            species=base.species,
            name=base.name,
            catch_time=base.catch_time,
            hp=self.my_hp.get(ct, base.hp),
            max_hp=self.my_max.get(ct, base.max_hp),
            skills=list(base.skills),
        )


async def drive_battle(
    client,
    policy: ActionPolicy,
    *,
    ready: bool = True,
    turn_wait: float = 2.0,
    switch_wait: float = 1.0,
    log: list[str] | None = None,
    context: LiveBattleContextBuilder | None = None,
    on_turn=None,
    on_frame=None,
    max_turns: int = 60,
    skill_names: dict[int, str] | None = None,
    resolve_skill: Any = None,
) -> BattleResult:
    """驱动一场对战：2404 准备 → 逐回合「回合开始→decide→执行→结算」→ 2506 结束。

    每个决策点：
      1) 构造 BattleContext（默认最小区间；传入 context 则按真实帧构建）；
      2) policy.decide(ctx) → Action；
      3) 执行：switch_to→2407 换宠（等对手 2505 判定主动/被动）、skill_id→2405 出招（结算）、potion→暂跳过。

    结束条件：收到 2506，或 policy 返回空 Action（操作表耗尽），或超过 max_turns。
    """
    res = BattleResult()
    loop = asyncio.get_running_loop()
    out = log if log is not None else []
    names = skill_names or {}

    # 技能名反查：本地战斗库优先，缺的（尤其 BOSS 被动/专属技，如「临时改良/工业套组」）
    # 交给 resolve_skill 在线兜底，失败静默返回空串，避免实时战报里敌方技能显示成裸 id。
    _resolved: dict[int, str] = {}

    def skill_label(sid: int | None) -> str:
        if sid is None:
            return ""
        n = names.get(sid)
        if n:
            return n
        if sid in _resolved:
            return _resolved[sid]
        if callable(resolve_skill):
            try:
                n = resolve_skill(sid)
            except Exception:
                n = None
            if n:
                _resolved[sid] = str(n)
                return _resolved[sid]
        _resolved[sid] = ""
        return ""

    active_catch: int | None = None
    turn = 0  # 已完成的回合数
    prev_enemy_hp: int | None = None
    status_names = _load_status_names()  # 异常状态 id -> 名称（实时注入用）

    def on_recv(f) -> None:
        out.append(f"  [recv] cmd={f.cmd} result={f.result} len={len(f.body)} body={f.body[:32].hex()}")
        rec = {"dir": "recv", "cmd": f.cmd, "result": f.result, "body": f.body.hex()}
        if f.cmd == FACTOR_WIN:      # 42390 只是「战斗结束」，胜利/战败都会发，不代表过关
            res.over = True
        if f.cmd == FACTOR_PASS:     # 45827 才是「因子过关推送」
            res.passed = True
        # 2505 结算帧顺带注入「敌方使用的技能 + 敌方血」，前端实时战报据此展示
        if f.cmd == Cmd.NOTE_USE_SKILL and context is not None:
            try:
                _en = _enemy_action_by_eid(f.body, context.enemy_eid, context.enemy_max_hp)
                if _en is None:
                    _en = _enemy_head_block(f.body, set(context.team))
                if _en is None:
                    _en = next((r for r in _settle_records(f.body, my_catches=set(context.team))
                                if r["role"] == "enemy"), None)
                if _en is not None:
                    rec["enemy_skill_id"] = _en["skill_id"]
                    rec["enemy_skill_name"] = skill_label(_en["skill_id"])
                    rec["enemy_hp"] = _en["hp"]
                    rec["enemy_max"] = _en["max_hp"]
                    ex = _read_action_extras(f.body, _en["off"])
                    if ex:
                        rec["enemy_is_crit"] = ex["is_crit"]
                        rec["enemy_status"] = _format_status_effects(ex["sides"], status_names)
                        rec["enemy_effect"] = _EFFECT_NAMES.get(ex["effect"], "")
                        rec["enemy_priority"] = ex.get("priority") or None
                        rec["enemy_gain_hp"] = ex.get("gain_hp") or None
                # 顺带注入「我方当前宠结算后的血/满血」，前端实时日志据此显示我方受到伤害
                if active_catch is not None:
                    _my = _my_action_by_catch(f.body, active_catch, turn + 1,
                                               context.my_max.get(active_catch))
                    if _my is not None:
                        rec["my_hp"] = _my["hp"]
                        rec["my_max"] = _my["max_hp"]
                        ex = _read_action_extras(f.body, _my["off"])
                        if ex:
                            rec["is_crit"] = ex["is_crit"]
                            rec["status"] = _format_status_effects(ex["sides"], status_names)
                            rec["my_effect"] = _EFFECT_NAMES.get(ex["effect"], "")
                            rec["my_priority"] = ex.get("priority") or None
                            rec["my_gain_hp"] = ex.get("gain_hp") or None
            except Exception:
                pass
        res.frames.append(rec)
        if on_frame is not None:
            on_frame(rec)
        if context is not None:
            context.feed(f)

    async def send(cmd: int, body: bytes) -> bool:
        try:
            await client.send(cmd, [body] if body else [])
        except (ConnectionError, asyncio.IncompleteReadError):
            return False
        out.append(f"[sent] cmd={cmd} body={body.hex()}")
        rec = {"dir": "send", "cmd": cmd, "body": body.hex()}
        if cmd == Cmd.USE_SKILL and len(body) >= 4:
            sid = struct.unpack_from(">I", body, 0)[0]
            rec["skill_id"] = sid
            if names.get(sid):
                rec["skill_name"] = names[sid]
        res.frames.append(rec)
        if on_frame is not None:
            on_frame(rec)
        return True

    # 开始对战：2404 → 等 2504
    if ready:
        if not await send(Cmd.READY_TO_FIGHT, b""):
            return res
        end = loop.time() + 3.0
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(client.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            on_recv(f)
            if f.cmd == FACTOR_PASS:
                res.passed = True
            if f.cmd == Cmd.NOTE_START_FIGHT:   # 2504 开战
                break

    if active_catch is None and context is not None and context.starter_catch is not None:
        active_catch = context.starter_catch
    # prev_enemy_hp 不在此预填：2504 扫描满血可能误判（如 7680），
    # 交给第 1 回合结算时用「动作块解析出的敌方满血」作为基准，避免算出假的“敌回血”。

    #对战-->  回合循环

    #对战-->  回合循环
    while turn < max_turns and not res.over:
        #构建当前上下文 并由回合驱动计算器 根据回合信息决定本回合的行动
        ctx = context.build(turn + 1, active_catch) if context is not None else _default_ctx(turn + 1, active_catch)
        #决定行动
        act = policy.decide(ctx)
        if act is None or (act.skill_id is None and act.switch_to is None and act.potion is None):
            out.append("[操作表] 无下一步操作，结束驱动")
            break

        if act.switch_to is not None:
            out.append(f"[操作表] {act.label()}")
            if not await send(Cmd.SWITCH_PET, _u32(act.switch_to)):
                break
            active_catch = act.switch_to
            saw_opponent_settle = False
            # 收集换宠回包：主动换宠会等到「对手 2505」（占回合）；被动换宠(死亡后)只有 2407 ack
            end = loop.time() + switch_wait
            while loop.time() < end:
                try:
                    f = await asyncio.wait_for(client.frames.get(), timeout=min(0.6, end - loop.time()))
                except asyncio.TimeoutError:
                    continue
                on_recv(f)
                if f.cmd == FACTOR_PASS:
                    res.passed = True
                if f.cmd == Cmd.FIGHT_OVER:
                    res.over = True
                    out.append("[战斗结束 2506]")
                    break
                if f.cmd == Cmd.NOTE_USE_SKILL:      # 对手结算 → 主动换宠(占回合)
                    saw_opponent_settle = True
                    break
            switch_kind = "active" if saw_opponent_settle else "passive"
            if context is not None:
                context.switch_kind = switch_kind
            out.append(f"[换宠] {switch_kind}（{'占回合' if saw_opponent_settle else '免费'}）")
            continue

        if act.potion is not None:
            out.append(f"[操作表] {act.label()}（吃药暂不支持，跳过）")
            continue

        # 出招 = 一个回合
        out.append(f"[操作表] 第{turn + 1}回合 {act.label()}")
        # 出招前冻结我方当前血，作为「本回合开始血」→ 结算后血即得「我方受到的伤害」
        my_hp_prev = context.my_hp.get(active_catch) if context else None
        if not await send(Cmd.USE_SKILL, _u32(act.skill_id)):
            break
        end = loop.time() + turn_wait
        settled = False
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(client.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            on_recv(f)
            if f.cmd == FACTOR_PASS:
                res.passed = True
            if f.cmd == Cmd.FIGHT_OVER:        # 2506 战斗结束
                res.over = True
                out.append("[战斗结束 2506]")
                break
            if f.cmd == Cmd.NOTE_USE_SKILL:    # 2505 本回合结算
                settled = True
                # 最后一回合时 2506(结束)/45827(过关) 会紧随 2505 之后，再短收一段避免漏掉
                drain_end = loop.time() + 0.5
                while loop.time() < drain_end:
                    try:
                        f2 = await asyncio.wait_for(client.frames.get(), timeout=min(0.3, drain_end - loop.time()))
                    except asyncio.TimeoutError:
                        break
                    on_recv(f2)
                    if f2.cmd == FACTOR_PASS:
                        res.passed = True
                    if f2.cmd == Cmd.FIGHT_OVER:
                        res.over = True
                        out.append("[战斗结束 2506]")
                        break
                break

        # 回合结束：把本回合结算实时写进战斗记录
        if settled:
            my_hp = context.my_hp.get(active_catch) if context else None
            my_max = context.my_max.get(active_catch) if context else None
            ehp = context.enemy_hp if context else None
            emax = context.enemy_max_hp if context else None
            esid = context.enemy_skill_id if context else None
            if ehp == 0:                     # 敌方结算后 0 血 = 已击败（过关）
                res.passed = True
            dmg = None
            delta = None
            prev = prev_enemy_hp if prev_enemy_hp is not None else emax
            if prev is not None and ehp is not None:
                dmg = max(0, prev - ehp)
                delta = ehp - prev
            my_delta = None
            damage_taken = None
            if my_hp is not None and my_hp_prev is not None:
                my_delta = my_hp - my_hp_prev
                damage_taken = max(0, my_hp_prev - my_hp)
            rec = {
                "turn": turn + 1,
                "skill_id": act.skill_id,
                "skill_name": names.get(act.skill_id, ""),
                "active_catch": active_catch,
                "switch_kind": context.switch_kind if context else None,
                "my_hp": my_hp, "my_max": my_max,
                "my_hp_prev": my_hp_prev, "my_hp_delta": my_delta, "damage_taken": damage_taken,
                "enemy_hp": ehp, "enemy_max": emax,
                "enemy_hp_prev": prev,
                "enemy_hp_delta": delta,
                "enemy_skill_id": esid,
                "enemy_skill_name": skill_label(esid),
                "damage": dmg,
            }
            res.turns.append(rec)
            if on_turn is not None:
                on_turn(rec)
            active_s = f"0x{active_catch:08x}" if active_catch is not None else "?"
            skl = act.skill_id
            skn = names.get(skl, "")
            sk_s = f"{skl}" + (f"({skn})" if skn else "")
            eskn = skill_label(esid)
            esk_s = f"{esid}({eskn})" if eskn else (f"{esid}" if esid is not None else "?")
            out.append(
                f"[回合{turn + 1}结算] 出招 {sk_s} | 敌用 {esk_s} | "
                f"我方 {active_s} {my_hp if my_hp is not None else '?'}/{my_max if my_max is not None else '?'} | "
                f"敌方 {ehp if ehp is not None else '?'}/{emax if emax is not None else '?'} | "
                f"敌受伤害~{dmg if dmg is not None else '?'}(敌血变化{delta if delta is not None else '?'})"
                f" | 我受伤害~{damage_taken if damage_taken is not None else '?'}(我血变化{my_delta if my_delta is not None else '?'})"
            )
            prev_enemy_hp = ehp
        turn += 1

    return res