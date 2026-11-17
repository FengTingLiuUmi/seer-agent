"""雷小伊对战方案（.cjc / .cjpt）解析与出招决策。

格式证据：``F:\\seer\\seer_cfg\\script\\method\\*`` 下的明文 GBK INI，
例如 ``王哈1.cjc`` / ``84.cjc``。同一文件可以有多个同名 ``[3022]`` section，
按出现顺序代表不同预设/仓库索引。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .battle_data import Pet
from .ini_util import as_bool, as_ids, as_int, load_ini


@dataclass(slots=True)
class PetPlan:
    pet_id: int
    section: str
    fields: dict[str, str] = field(default_factory=dict)
    is_ref: bool = False

    @property
    def cycle_skills(self) -> list[int]:
        return as_ids(self.fields.get("循环技能"))

    @property
    def cycle_counts(self) -> list[int]:
        return as_ids(self.fields.get("循环次数")) or [1] * len(self.cycle_skills)

    @property
    def use_skill(self) -> int:
        return as_int(self.fields.get("使用技能"), 0)

    @property
    def condition(self) -> str:
        return self.fields.get("出招条件", "")

    @property
    def compare(self) -> int:
        return as_int(self.fields.get("比较方式"), 0)

    @property
    def compare_value(self) -> int:
        return as_int(self.fields.get("比较值"), 0)

    @property
    def potion(self) -> int | None:
        return as_int(self.fields.get("吃药1内容"), 0) if as_bool(self.fields.get("吃药1")) else None

    @property
    def dispel_skill(self) -> int | None:
        if not as_bool(self.fields.get("消强")):
            return None
        return as_int(self.fields.get("消强技能"), 0) or None

    @property
    def warehouse_index(self) -> int:
        return as_int(self.fields.get("仓库索引"), 0)

    @property
    def must(self) -> bool:
        return as_bool(self.fields.get("必须"))

    @property
    def no_heal(self) -> bool:
        return as_bool(self.fields.get("不压血"))

    def choose(self, pet: Pet, opponent: Pet, turn: int) -> int | None:
        """返回技能 ID；负数表示特殊动作：-1 吃药、-2 切精灵。"""
        if self.potion and pet.max_hp and pet.hp / pet.max_hp < 0.5:
            return -1
        if self.dispel_skill and sum(max(0, v) for v in opponent.boosts.values()) > 0:
            return self.dispel_skill
        if self.condition and _eval_condition(self, pet, opponent, turn):
            if self.use_skill:
                return self.use_skill
        skills = self.cycle_skills
        if skills:
            counts = self.cycle_counts
            total = max(1, sum(counts))
            idx = (max(0, turn - 1)) % total
            acc = 0
            for sid, cnt in zip(skills, counts + [1] * len(skills)):
                acc += max(1, cnt)
                if idx < acc:
                    return sid
        if self.use_skill:
            return self.use_skill
        return pet.skills[0] if pet.skills else None


def _eval_condition(plan: PetPlan, pet: Pet, opponent: Pet, turn: int) -> bool:
    cond = plan.condition
    cmpmode = plan.compare
    value = plan.compare_value
    if "对方强化" in cond:
        lhs = sum(max(0, v) for v in opponent.boosts.values())
    elif "我方血量" in cond or "自身血量" in cond:
        lhs = pet.hp
    elif "对方血量" in cond:
        lhs = opponent.hp
    elif "回合" in cond:
        lhs = turn
    elif "PP" in cond:
        lhs = 0
    else:
        return False
    if cmpmode == 0:
        return lhs >= value
    if cmpmode == 1:
        return lhs <= value
    if cmpmode == 2:
        return lhs < value
    if cmpmode == 3:
        return lhs > value
    return lhs >= value


@dataclass(slots=True)
class BattlePlan:
    path: Path
    plans: list[PetPlan] = field(default_factory=list)
    refs: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "BattlePlan":
        p = Path(path)
        doc = load_ini(p)
        out = cls(path=p)
        for sec, kv in doc.sections:
            if not sec:
                continue
            if sec.endswith(".cjpt") or "六界" in sec or "克罗" in sec:
                out.refs[sec] = kv
                continue
            try:
                pid = int(sec)
            except ValueError:
                out.refs[sec] = kv
                continue
            out.plans.append(PetPlan(pid, sec, kv))
        return out

    def by_pet(self, pet_id: int, index: int = 0) -> PetPlan | None:
        matches = [p for p in self.plans if p.pet_id == pet_id]
        if not matches:
            return None
        return matches[min(index, len(matches) - 1)]

    def team(self) -> list[PetPlan]:
        """按文件顺序取每个 section；重复 ID 视为不同预设。"""
        return list(self.plans)


def load_plan(path: str | Path) -> BattlePlan:
    return BattlePlan.load(path)