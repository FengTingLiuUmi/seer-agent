"""本地战斗模拟与观测。

目标不是逐字节复刻官方战斗服务器，而是复刻 2.0.9 的“本地战斗引擎 + 出招记录”
能力：能按 .cjc 方案出招、按属性/威力/强化/常见 BOSS 特性结算，并输出与
``日常记录/出招记录/ACCOUNT.txt`` 同构的可读战报。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from .battle_data import BattleData, BossTrait, Move, Pet
from .cjc import BattlePlan, PetPlan


@dataclass(slots=True)
class BattleEvent:
    turn: int
    kind: str
    text: str
    data: dict = field(default_factory=dict)


@dataclass(slots=True)
class PetState:
    """一帧精灵状态快照，供战斗窗口绘制。"""
    id: int
    name: str
    hp: int
    max_hp: int
    alive: bool
    boosts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "alive": self.alive,
            "boosts": dict(self.boosts),
        }


@dataclass(slots=True)
class TurnSnapshot:
    """一个回合的完整画面：双方状态 + 本回合文本。"""
    turn: int
    player: list[PetState] = field(default_factory=list)
    enemy: list[PetState] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "turn": self.turn,
            "player": [p.as_dict() for p in self.player],
            "enemy": [p.as_dict() for p in self.enemy],
            "texts": list(self.texts),
        }


@dataclass(slots=True)
class BattleResult:
    winner: str
    turns: int
    events: list[BattleEvent]
    log_lines: list[str]
    snapshots: list[TurnSnapshot] = field(default_factory=list)

    def write_log(self, path: str | Path) -> None:
        Path(path).write_text("\n".join(self.log_lines) + "\n", encoding="utf-8")


class Battle:
    def __init__(
        self,
        data: BattleData,
        player_team: list[Pet],
        enemy_team: list[Pet],
        *,
        plan: BattlePlan | None = None,
        moves: dict[int, int] | None = None,
        seed: int = 20260909,
        boss_traits: list[BossTrait] | None = None,
        title: str = "本地战斗",
    ):
        self.data = data
        self.player_team = player_team
        self.enemy_team = enemy_team
        self.plan = plan
        self.moves = moves  # species_id -> 固定技能 id；父 agent 下发的单关出招预设
        self.rng = random.Random(seed)
        self.boss_traits = boss_traits or []
        self.title = title
        self.events: list[BattleEvent] = []
        self.lines: list[str] = []
        self.snapshots: list[TurnSnapshot] = []
        self.turn = 0
        self._plan_index: dict[int, int] = {}
        self._turn_start = 0

    # ------------------------------------------------------------------
    def active(self, team: list[Pet]) -> Pet | None:
        for p in team:
            if p.alive:
                return p
        return None

    def run(self, *, max_turns: int = 50) -> BattleResult:
        self._log(f"【战斗】{self.title}")
        p = self.active(self.player_team)
        e = self.active(self.enemy_team)
        if p is None or e is None:
            winner = "player" if e is None else "enemy"
            return BattleResult(winner, 0, self.events, self.lines, self.snapshots)
        self._log(f"【我方精灵组】{p.species.id}  ({p.name})")
        self._log(f"(对方精灵组){e.species.id}  ({e.name})")
        for i, t in enumerate(self.boss_traits, 1):
            self._log(f"BOSS特性[{i}]：{t.text} id：{t.id} 参数：{' '.join(map(str, t.args))}")

        winner = "draw"
        for turn in range(1, max_turns + 1):
            self.turn = turn
            p = self.active(self.player_team)
            e = self.active(self.enemy_team)
            if p is None:
                winner = "enemy"
                break
            if e is None:
                winner = "player"
                break
            self._log(f"--------------------------- 当前回合：{turn} ---------------------------")
            self._turn_start = len(self.events)
            self._boss_turn_start(p, e)

            p_move = self._choose_player_move(p, e)
            e_move = self._choose_enemy_move(p, e)
            actions = []
            if p_move is not None:
                actions.append((p, e, p_move, "player"))
            if e_move is not None:
                actions.append((e, p, e_move, "enemy"))
            actions.sort(key=lambda a: (-self._priority(a[0], a[2]), -self._speed(a[0])))
            for actor, target, move, side in actions:
                if not actor.alive or not target.alive:
                    continue
                self._execute(actor, target, move, side)
                if not target.alive:
                    self._log(f"({target.side}) {target.name}[{target.species.id}] 已死亡")
                if not self.active(self.player_team) or not self.active(self.enemy_team):
                    break
            self._snapshot(turn)

        p = self.active(self.player_team)
        e = self.active(self.enemy_team)
        if winner == "draw":
            winner = "player" if e is None and p is not None else ("enemy" if p is None else "draw")
        self._log("---------------------------- 对战结束 -----------------------------")
        self._log(f"【{'胜利' if winner == 'player' else '失败' if winner == 'enemy' else '平局'}】 总回合：{self.turn}")
        return BattleResult(winner, self.turn, self.events, self.lines, self.snapshots)

    # ------------------------------------------------------------------
    def _choose_player_move(self, p: Pet, e: Pet) -> int | None:
        # 父 agent 下发的固定出招预设优先
        if self.moves and p.species.id in self.moves:
            return self.moves[p.species.id]
        if self.plan:
            plan = self.plan.by_pet(p.species.id, self._plan_index.get(p.species.id, 0))
            if plan:
                sid = plan.choose(p, e, self.turn)
                if sid is not None:
                    return sid
        return p.skills[0] if p.skills else None

    def _choose_enemy_move(self, p: Pet, e: Pet) -> int | None:
        if not e.skills:
            return None
        moves = [self.data.moves.get(s) for s in e.skills]
        moves = [m for m in moves if m]
        if not moves:
            return e.skills[0]
        # 简单 AI：优先最高威力攻击技能，其次属性技能
        attacks = [m for m in moves if m.category in (1, 2) and m.power > 0]
        if attacks:
            return max(attacks, key=lambda m: m.power).id
        return moves[0].id

    def _priority(self, actor: Pet, move_id: int) -> int:
        m = self.data.moves.get(move_id)
        base = m.priority if m else 0
        for t in self.boss_traits if actor.side == "enemy" else []:
            if "先制+" in t.text:
                import re
                mm = re.search(r"先制\+(\d+)", t.text)
                if mm:
                    base += int(mm.group(1))
        return base

    def _speed(self, p: Pet) -> int:
        stage = p.boosts.get("spd", 0)
        return int(p.stats.get("spd", 1) * _stage_mult(stage))

    def _execute(self, actor: Pet, target: Pet, move_id: int, side: str) -> None:
        m = self.data.moves.get(move_id)
        if m is None:
            return
        label = "【我方" if side == "player" else "(对方"
        suffix = "】" if side == "player" else ")"
        cat = {1: "物攻", 2: "特攻", 3: "属性"}.get(m.category, "?")
        self._log(f"{label}{self._boost_prefix(actor)} {actor.name}[{actor.species.id}] 使用1次 {cat} {m.name}[{m.id}] 威力:{m.power} {self._type_name(m.type)}")
        if m.category == 3:
            self._apply_effects(actor, target, m, side, damage=0)
            return
        if not self._hit(actor, target, m):
            self._log("技能未命中")
            return
        crit = self.rng.random() * 100 < m.crit_rate and not self._boss_immune_crit(target)
        damage = self._damage(actor, target, m, crit=crit)
        damage = self._boss_modify_damage(target, damage)
        target.hp = max(0, target.hp - damage)
        if target.hp <= 0:
            target.fainted = True
        extra = "【暴击】" if crit else ""
        target_label = "对方" if side == "player" else "我方"
        target_side = "enemy" if side == "player" else "player"
        if target.hp <= 0:
            extra += f"({target_label}死亡)"
        self._log(f"造成了{damage}点伤害{extra}，{target_label}剩余{target.hp}/{target.max_hp}")
        self._apply_effects(actor, target, m, side, damage=damage)

    def _hit(self, actor: Pet, target: Pet, m: Move) -> bool:
        if m.must_hit:
            return True
        for t in self.boss_traits if actor.side == "enemy" else []:
            if "必中" in t.text:
                return True
        return self.rng.random() * 100 < m.accuracy

    def _damage(self, actor: Pet, target: Pet, m: Move, *, crit: bool) -> int:
        atk_key = "sp_atk" if m.category == 2 else "atk"
        def_key = "sp_def" if m.category == 2 else "def"
        atk = actor.stats.get(atk_key, 1) * _stage_mult(actor.boosts.get(atk_key, 0))
        dfn = target.stats.get(def_key, 1) * _stage_mult(target.boosts.get(def_key, 0))
        base = ((2 * actor.level / 5 + 2) * max(1, m.power) * atk / max(1, dfn)) / 50 + 2
        stab = 1.5 if m.type == actor.species.type else 1.0
        typ = self.data.type_multiplier(m.type, target.species.type)
        crit_mul = 2.0 if crit else 1.0
        rand = self.rng.uniform(0.85, 1.0)
        return max(1, int(base * stab * typ * crit_mul * rand))

    # ------------------------------------------------------------------
    def _apply_effects(self, actor: Pet, target: Pet, m: Move, side: str, *, damage: int) -> None:
        for eid in m.side_effects:
            kv = self.data.effects.get(eid, {})
            tag = kv.get("tagA", "")
            info = kv.get("info", "")
            text = tag + info
            if "恢复" in text and damage:
                heal = max(1, damage // 2)
                actor.hp = min(actor.max_hp, actor.hp + heal)
                self._log(f"恢复{heal}点体力")
            if "消强" in text:
                for k in target.boosts:
                    target.boosts[k] = 0
                self._log("消除对方能力提升")
            if "解弱" in text:
                for k, v in list(actor.boosts.items()):
                    if v < 0:
                        actor.boosts[k] = 0
                self._log("解除自身能力下降")
            if "强化" in text:
                for k in ("atk", "sp_atk", "def", "sp_def", "spd"):
                    actor.boosts[k] = min(6, actor.boosts.get(k, 0) + 1)
                self._log("自身全属性+1")
            if "弱化" in text:
                for k in ("atk", "sp_atk", "def", "sp_def", "spd"):
                    target.boosts[k] = max(-6, target.boosts.get(k, 0) - 1)
                self._log("对方全属性-1")
            for st in ("烧伤", "中毒", "麻痹", "害怕", "睡眠", "疲惫", "冻伤"):
                if st in text and not self._boss_immune_status(target):
                    target.status.add(st)
                    self._log(f"对方进入{st}状态")

    def _boss_immune_status(self, target: Pet) -> bool:
        if target.side != "enemy":
            return False
        return any("免疫异常" in t.text for t in self.boss_traits)

    def _boss_immune_crit(self, target: Pet) -> bool:
        if target.side != "enemy":
            return False
        return any("免爆" in t.text or "免疫致命" in t.text for t in self.boss_traits)

    def _boss_modify_damage(self, target: Pet, damage: int) -> int:
        if target.side != "enemy":
            return damage
        for t in self.boss_traits:
            import re
            m = re.search(r"免疫低于(\d+)", t.text)
            if m and damage < int(m.group(1)):
                return 0
            m = re.search(r"免疫高于(\d+)", t.text)
            if m and damage > int(m.group(1)):
                return 0
            if "免疫物理" in t.text:
                pass
        return damage

    def _boss_turn_start(self, p: Pet, e: Pet) -> None:
        if not self.boss_traits:
            return
        import re
        for t in self.boss_traits:
            m = re.search(r"每回合附加(\d+)点固定伤害", t.text)
            if m:
                d = int(m.group(1))
                p.hp = max(0, p.hp - d)
                self._log(f"BOSS特性【{t.text.split('：')[0]}】造成{d}点固定伤害，我方剩余{p.hp}/{p.max_hp}")
            m = re.search(r"每回合恢复自身(\d+)点体力", t.text)
            if m:
                e.hp = min(e.max_hp, e.hp + int(m.group(1)))
            m = re.search(r"每回合双防\+(\d+)", t.text)
            if m:
                e.boosts["def"] = min(6, e.boosts.get("def", 0) + int(m.group(1)))
                e.boosts["sp_def"] = min(6, e.boosts.get("sp_def", 0) + int(m.group(1)))
            if "对手每回合全属性-1" in t.text:
                for k in p.boosts:
                    p.boosts[k] = max(-6, p.boosts.get(k, 0) - 1)

    # ------------------------------------------------------------------
    def _type_name(self, type_id: int) -> str:
        from .battle_data import TYPE_NAMES
        return TYPE_NAMES.get(type_id, str(type_id))

    def _boost_prefix(self, p: Pet) -> str:
        positive = [k for k, v in p.boosts.items() if v > 0]
        if not positive:
            return ""
        return "1.25"  # 与 2.0.9 战报的 1.25 标记近似；真实倍率由强化项决定

    def _log(self, text: str) -> None:
        self.lines.append(text)
        self.events.append(BattleEvent(self.turn, "log", text))

    def _snapshot(self, turn: int) -> None:
        texts = [e.text for e in self.events[self._turn_start:]]
        self.snapshots.append(
            TurnSnapshot(
                turn=turn,
                player=[_pet_state(p) for p in self.player_team],
                enemy=[_pet_state(p) for p in self.enemy_team],
                texts=texts,
            )
        )


def _pet_state(p: Pet) -> PetState:
    return PetState(
        id=p.species.id,
        name=p.name or p.species.name,
        hp=p.hp,
        max_hp=p.max_hp,
        alive=p.alive,
        boosts=dict(p.boosts),
    )


def _stage_mult(stage: int) -> float:
    stage = max(-6, min(6, stage))
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def simulate(
    data_root: str | Path,
    *,
    player_ids: list[int],
    enemy_ids: list[int],
    plan_path: str | Path | None = None,
    moves: dict[int, int] | None = None,
    boss_traits: list[BossTrait] | None = None,
    seed: int = 20260909,
    max_turns: int = 50,
) -> BattleResult:
    data = BattleData(data_root)
    plan = BattlePlan.load(plan_path) if plan_path else None
    players = [data.make_pet(i, side="player") for i in player_ids]
    enemies = [data.make_pet(i, side="enemy") for i in enemy_ids]
    return Battle(data, players, enemies, plan=plan, moves=moves, boss_traits=boss_traits, seed=seed).run(max_turns=max_turns)