"""操作表能力（出战决策器）：「回合开始」给上下文 → 算出下一步操作。

定位：
  - 这是"操作表"的抽象层，独立于回合状态机与网络执行。
  - 回合状态机在每回合开始时构造 BattleContext，调用 ActionPolicy.decide()，
    拿到 Action 再去执行（出招 2405 / 换宠 2407 / 吃药）。

参考雷小伊：
  - seer_rebuild/cjc.py 的 PetPlan.choose(pet, opponent, turn) 已经是这种
    「条件 + 循环技能 + 吃药 + 消强」的出招规则引擎；负返回值表示特殊动作。
  - 本模块只做最简版（ScriptedPolicy 固定序列），但接口与升级路径保留好：
    未来 LLMPolicy 只需实现同一个 decide(ctx) -> Action。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class Action:
    """下一步操作（决策结果）。三者通常只填一个。"""
    skill_id: int | None = None    # 出招（2405）
    switch_to: int | None = None   # 换宠 catch_time（2407）
    potion: int | None = None      # 吃药（道具 id），简单版暂不执行

    def label(self) -> str:
        if self.skill_id is not None:
            return f"出招 {self.skill_id}"
        if self.switch_to is not None:
            return f"换宠 0x{self.switch_to:08x}"
        if self.potion is not None:
            return f"吃药 {self.potion}"
        return "空操作"


@dataclass(slots=True)
class SkillInfo:
    """一个可用技能及其 PP。"""
    id: int
    name: str = ""
    pp: int | None = None       # 剩余/当前 PP；未知为 None


@dataclass(slots=True)
class PetInfo:
    """单只精灵的当前快照。可换精灵列表里的每一项也是它。"""
    species: int
    name: str = ""
    catch_time: int | None = None
    hp: int | None = None
    max_hp: int | None = None
    skills: list[SkillInfo] = field(default_factory=list)   # 可用技能 + PP


@dataclass(slots=True)
class BattleContext:
    """「回合开始」提供给操作表的完整上下文。"""
    turn: int                       # 第几回合（1-based）
    active: PetInfo                 # 当前在场精灵
    bench: list[PetInfo]            # 可换精灵（含当前，供换宠决策）
    enemy: PetInfo | None = None    # 敌方当前信息（best-effort）
    round_info: dict = field(default_factory=dict)  # 其它回合信息（强化/状态等，best-effort）


class ActionPolicy(Protocol):
    """操作表能力接口。

    未来升级大模型驱动：实现一个 LLMPolicy，把 BattleContext 序列化喂给模型，
    返回 Action JSON 即可，调用方完全不变。
    """
    def decide(self, ctx: BattleContext) -> Action: ...


class ScriptedPolicy:
    """简单操作表：固定「出招/换宠」序列。

    默认走一遍就结束（返回空 Action）；``loop=True`` 时按循环技能反复使用。
    要更丰富（按条件出招/吃药/消强/压血）时，参考 cjc.PetPlan.choose() 在本类的
    decide() 里扩展即可。
    """
    def __init__(self, sequence: list[Action] | None = None, *, loop: bool = False):
        self.sequence = list(sequence or [])
        self.loop = loop
        self._i = 0

    def decide(self, ctx: BattleContext) -> Action:
        # 没预设：用当前精灵第一个可用技能（最保守兜底）
        if not self.sequence:
            if ctx.active.skills:
                return Action(skill_id=ctx.active.skills[0].id)
            return Action()
        if not self.loop and self._i >= len(self.sequence):
            return Action()   # 固定序列消费完 → 空操作（结束）
        act = self.sequence[self._i % len(self.sequence)]
        self._i += 1
        return act

    def reset(self) -> None:
        self._i = 0