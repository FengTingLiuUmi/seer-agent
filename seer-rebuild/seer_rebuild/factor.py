"""精灵因子（打因子）数据模型。

数据来源（2026-11 修正）：`F:\seer\seer_cfg\json\Fragments.ini`（本地因子表）
+ seerapi 的 `factor` / `factor_design` 两个资源。

关系：
  - 每个目标精灵对应一个 **factor**（factor_id），例如
    `2400532 谜之英雄因子` → target 精灵 4848；
    `2400338 灵巢之主·索杰德尔因子` → target 精灵 4599。
  - factor 挂在 **factor_design**（design_id）上，design 里定义：
      * `time_value / progress_value / fail_times`：读状态用的 46046 forever 键；
      * `difficulties{easy,normal,hard}`：每个难度各 5 个 task（关卡），
        `task.boss_pet.id` = 该关 BOSS 的 species；
      * 关卡规则（normal 有 6 回合限制、hard 有不可重复上阵 / 100 级 / 失败 3 次）。

  - 打一关 = 换阵容 → 46046 读进度 → 42396 发起 PVE BOSS 战 → 2404 准备 →
    2405 出招 → S2C 2506 结束 → 41413 领取。

重要（未校准）：`42396` 的 body 第 1 个 u32 是「关卡 id」（实测旧包为 0x6f=111），
它**不等于** boss species、factor_id 或 design_id，当前在 seerapi/本地表里
反查不到该映射，需要抓一只真·因子战斗的包来校准（见 `docs/逆向分析.md` 2.7）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .commands import Cmd
from .features import FeatureStep, u32

# 因子战斗命令（命令号统一在 commands.Cmd 里维护，这里只做可读别名）
PET_CURE_FREE = Cmd.PET_CURE_FREE          # 免费治疗（战前/战后）
FIGHT_H5_PVE_BOSS = Cmd.FIGHT_H5_PVE_BOSS   # 发起 PVE BOSS 战：body=[关卡id][1][1]
READY_TO_FIGHT = Cmd.READY_TO_FIGHT         # 准备战斗：空 body，S2C 回 4B seed
USE_SKILL = Cmd.USE_SKILL                   # 出招：body=[技能id]
SWITCH_PET = Cmd.SWITCH_PET                 # 战斗内切换精灵：body=[catch_time]
FIGHT_OVER = Cmd.FIGHT_OVER                 # S2C 战斗结束
FACTOR_ACTION = Cmd.FACTOR_ACTION           # 因子动作/领取
GET_MULTI_FOREVER = Cmd.GET_MULTI_FOREVER   # 读 forever（进度/次数/失败次数）
STAGE_LIST = Cmd.STAGE_LIST                 # 图鉴/收集进度列表，不是因子关卡表

# 官方 Unity 端「进入因子关 → 开始战斗」的两个命令
FACTOR_ENTER_STAGE = Cmd.FACTOR_ENTER_STAGE   # 进入因子关：body=[design_id][difficulty]
FACTOR_START_BATTLE = Cmd.FACTOR_START_BATTLE # 开始因子战斗：body=[design_id][difficulty]

# 难度锚定本体（pve:difficulty 受控词表 ⇄ SeerAPI level ⇄ 客户端 int ⇄ 46046 低16位标记）。
# 唯一事实源是 factor_design.difficulties[].level ∈ {easy, normal, hard}，
# 客户端 int = easy→1 / normal→2 / hard→3；46046 进度低16位 = 0x100/0x200/0x400 同序自证。
# 不要再手写「1=简单 2=普通 3=困难」这类会和社区叫法打架的自由文本（社区的「困难」=normal=2）。
DIFFICULTY_LABEL_TO_INT = {"简单": 1, "困难": 2, "地狱": 3}   # 社区/论坛叫法（SSOT 中文 label）
DIFFICULTY_LEVEL_TO_INT = {"easy": 1, "normal": 2, "hard": 3}  # SeerAPI level 键


def difficulty_int(spec: str | int) -> int:
    """把「社区难度名 / SeerAPI level / 已给 int」统一解析成 41284/41282 的难度 int。

    锚定本体：简单=easy=1 / 困难=normal=2 / 地狱=hard=3（对应 46046 0x100/0x200/0x400）。
    未知值直接抛错，不静默落回默认值——避免再出现「把地狱当成 2」这类静默错档。
    """
    if isinstance(spec, int) and not isinstance(spec, bool):
        if spec in (1, 2, 3):
            return spec
        raise ValueError(f"难度 int 越界: {spec}（合法 1/2/3 = easy/normal/hard）")
    s = str(spec).strip()
    for m in (DIFFICULTY_LABEL_TO_INT, DIFFICULTY_LEVEL_TO_INT):
        if s in m:
            return m[s]
    raise ValueError(f"未知难度: {spec!r}（受控词表：简单/困难/地狱 或 easy/normal/hard）")


@dataclass(slots=True)
class FactorSpec:
    """一个目标精灵的因子关完整参数。"""
    factor_id: int
    name: str
    design_id: int
    target_species: int
    time_value: int
    progress_value: int
    fail_times: int
    bosses: list[int]                          # 5 关 BOSS species（同序）
    boss_names: dict[int, str] = field(default_factory=dict)
    difficulty: str = "normal"
    forever_progress_keys: list[int] = field(default_factory=list)
    single_pet_stages: frozenset[int] = frozenset({3})  # 单精灵关（1 基；实测第 3 关通常是 1v1，不可 2407 切换）

    def __post_init__(self):
        if not self.forever_progress_keys:
            self.forever_progress_keys = [self.progress_value, self.time_value, self.fail_times]

    def boss_name(self, species: int) -> str:
        return self.boss_names.get(species, str(species))

    def as_dict(self) -> dict:
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "design_id": self.design_id,
            "target_species": self.target_species,
            "time_value": self.time_value,
            "progress_value": self.progress_value,
            "fail_times": self.fail_times,
            "difficulty": self.difficulty,
            "stages": [
                {"index": i + 1, "boss_species": b, "boss_name": self.boss_name(b)}
                for i, b in enumerate(self.bosses)
            ],
        }


# 不再内置「当前因子」或「已知因子表」：打哪个因子必须由调用方显式给出
# factor_id（41413 领取 / 动态拉 spec）或 design_id（41284/41282 进关）。

_DYNAMIC_CACHE: dict[int, FactorSpec] = {}


def load_factor_spec(factor_id: int, provider=None) -> FactorSpec | None:
    """从 seerapi 动态拉取 factor → factor_design，构造 FactorSpec（运行时缓存）。

    顺序：`get factor <id>` → `design.id` → `get factor_design <id>` →
    取 time/progress/fail forever 键 + normal 难度的 5 个 task.boss_pet.id。
    """
    if factor_id in _DYNAMIC_CACHE:
        return _DYNAMIC_CACHE[factor_id]
    if provider is None:
        from .provider import SeerApiProvider
        provider = SeerApiProvider()
    try:
        f = provider.get("factor", factor_id)
        if not f:
            return None
        design_id = (f.get("design") or {}).get("id")
        d = provider.get("factor_design", design_id) if design_id else None
        if not d:
            return None
        bosses: list[int] = []
        for lvl in d.get("difficulties", []):
            if lvl.get("level") != "normal":
                continue
            bosses = [t["boss_pet"]["id"] for t in lvl.get("tasks", [])]
            break
        spec = FactorSpec(
            factor_id=factor_id,
            name=f.get("name") or str(factor_id),
            design_id=int(design_id),
            target_species=(f.get("pet") or {}).get("id") or 0,
            time_value=int(d.get("time_value") or 0),
            progress_value=int(d.get("progress_value") or 0),
            fail_times=int(d.get("fail_times") or 0),
            bosses=bosses,
        )
        _DYNAMIC_CACHE[factor_id] = spec
        return spec
    except Exception:
        return _DYNAMIC_CACHE.get(factor_id)


def forever_keys(*, design_id: int | None = None, factor_id: int | None = None, provider=None) -> list[int]:
    """46046 读因子进度的 forever 键 `[progress, time, fail]`。

    必须显式给出 ``design_id`` 或 ``factor_id``；都没有则返回空列表（调用方应报错）。
    """
    if factor_id is not None:
        spec = load_factor_spec(factor_id, provider=provider)
        if spec:
            return spec.forever_progress_keys
    if design_id is not None:
        if provider is None:
            from .provider import SeerApiProvider
            provider = SeerApiProvider()
        try:
            d = provider.get("factor_design", design_id)
            if d:
                return [
                    int(d.get("progress_value") or 0),
                    int(d.get("time_value") or 0),
                    int(d.get("fail_times") or 0),
                ]
        except Exception:
            pass
    return []


def describe_spec(spec: FactorSpec | None = None) -> str:
    if spec is None:
        return "(未指定因子)"
    lines = [f"{spec.name}（factor_id={spec.factor_id} design={spec.design_id}）"]
    for i, b in enumerate(spec.bosses, 1):
        lines.append(f"  第{i}关 BOSS={b}({spec.boss_name(b)})")
    lines.append(f"  forever: progress={spec.progress_value} time={spec.time_value} fail={spec.fail_times}")
    return "\n".join(lines)


def factor_fight_steps(*, boss_id: int | None = None, skill_id: int | None = None) -> list[FeatureStep]:
    """真机发起一场因子关 PVE 战斗（含一次出招）。

    42396 body 形如 [关卡id][1][1]；2404 空；2405 body=[技能id]。
    （lxy_yz_2 的雷小伊旧方法；官方端用 ``factor_enter_steps`` 的 41284/41282。）
    """
    steps: list[FeatureStep] = [
        FeatureStep("免费治疗", PET_CURE_FREE, b"", False, "PET_CURE_FREE"),
    ]
    if boss_id is not None:
        steps.append(FeatureStep("发起PVE BOSS战", FIGHT_H5_PVE_BOSS, u32(boss_id) + u32(1) + u32(1), True, "FIGHT_H5_PVE_BOSS"))
    steps.append(FeatureStep("准备战斗", READY_TO_FIGHT, b"", False, "READY_TO_FIGHT"))
    if skill_id is not None:
        steps.append(FeatureStep("出招", USE_SKILL, u32(skill_id), True, "USE_SKILL"))
    return steps


def factor_enter_steps(*, design_id: int, difficulty: int | str = 1) -> list[FeatureStep]:
    """官方 Unity 端进入因子关并开始战斗（unity_mzyx / unity_yz_battle 实证）。

    41284 = 进入因子关，41282 = 开始因子战斗；body 均 = [design_id][difficulty]。
    ``difficulty`` 传「简单/困难/地狱」「easy/normal/hard」或 1/2/3，统一经
    :func:`difficulty_int` 归一：1=简单(easy) / 2=困难(normal) / 3=地狱(hard)。
    **第几关（BOSS）由服务端按账号进度自动推进，客户端不传**。之后官方端进
    2441 加载 → 战斗观测，无需 42396 关卡 id。
    """
    difficulty = difficulty_int(difficulty)
    body = u32(design_id) + u32(difficulty)
    return [
        FeatureStep("进入因子关", FACTOR_ENTER_STAGE, body, True, "FACTOR_ENTER_STAGE"),
        FeatureStep("开始因子战斗", FACTOR_START_BATTLE, body, True, "FACTOR_START_BATTLE"),
    ]


def battle_loop_steps(*, skills: list[int], switches: list[int] | None = None) -> list[FeatureStep]:
    """官方 Unity 端出招循环（unity_yz_battle.pcapng 实证）。

    2404 准备 → 之后每个回合 2405 出招[技能id]；出招后可 2407 切换精灵[catch_time]
    再出下一招。``switches`` 比 ``skills`` 少一个（第 1 招用场上精灵，不用切）。
    """
    steps: list[FeatureStep] = [FeatureStep("准备战斗", READY_TO_FIGHT, b"", False, "READY_TO_FIGHT")]
    for i, sid in enumerate(skills):
        steps.append(FeatureStep("出招", USE_SKILL, u32(sid), True, "USE_SKILL"))
        if switches and i < len(switches):
            steps.append(FeatureStep("切换精灵", SWITCH_PET, u32(switches[i]), True, "SWITCH_PET"))
    return steps


def factor_progress(forever_values: list[int]) -> int:
    """从 46046 因子响应解析「当前打到第几关（0 基）」。

    46046 查 spec.forever_progress_keys 的响应是 N 个 forever 值；
    第 1 位是 progress_value（当前关数，0 基）。保留旧传参签名。
    """
    if not forever_values:
        return 0
    return forever_values[0]