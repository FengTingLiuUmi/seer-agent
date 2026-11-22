"""战斗战报：把一场真实战斗的 C2S/S2C 帧 + 阵容/装备快照，整理成可复盘的结构化战报。

数据来源（三者在同一场战斗会话中采集）：
  - 阵容：`pets.read_bag`（43706），正式顺序即 首发出战顺序；
  - 装备/称号/装扮：`inventory.snapshot_from_live`（1001 登录快照，已修复丢弃 bug）；
  - 出招/换宠：C2S 命令日志（2404 准备 / 2405 出招[技能id] / 2407 换宠[catch_time]）；
  - 血量（双方）：S2C 2504（开场血）/ 2505（技能结算后血），逐字节扫描 catch 与满血标记。

“异常状态”字段目前为 best-effort：从技能/结算帧里可稳定识别的仅有我方出招序列，
状态图标/状态名编码尚未完全逆向，本模块对无法确认的状态一律标空并给出说明。
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# C2S / S2C 命令号
C2S_READY = 2404
C2S_SKILL = 2405
C2S_SWITCH = 2407
S2C_INIT = 2503          # 战斗初始化（双方整队 + 技能 + 初始血）
S2C_START = 2504         # 开战（登场的双方精灵 + 血）
S2C_SKILL = 2505         # 技能结算（出招 + 双方血变动）
S2C_OVER = 2506          # 战斗结束
S2C_EVENT = 2595         # 回合事件/动画（部分异常状态在此）
S2C_WIN = 42390          # 因子胜利
S2C_PROGRESS = 45827     # 因子进度推送

CATCH_LO = 0x54000000    # catch_time unix 秒合理范围
CATCH_HI = 0x6C000000


def _u32(b: bytes, off: int) -> int | None:
    return struct.unpack_from(">I", b, off)[0] if len(b) >= off + 4 else None


def _s32(b: bytes, off: int) -> int | None:
    return struct.unpack_from(">i", b, off)[0] if len(b) >= off + 4 else None


def _u16(b: bytes, off: int) -> int | None:
    return struct.unpack_from(">H", b, off)[0] if len(b) >= off + 2 else None


def _u8(b: bytes, off: int) -> int | None:
    return b[off] if 0 <= off < len(b) else None


# TRAIT(能力变化) 的 id -> 名称（EffectInfoParamType.ini [0]/[2]/[16]/[24]）
_ABILITY_NAMES = ("攻击", "防御", "特攻", "特防", "速度", "命中")

# 属性克制关系（FightEffectName.as）
_EFFECT_NAMES = {1: "无效", 2: "微弱", 3: "克制"}

# 异常状态(ABNORMAL) 的 id -> 名称（battle_effects.ini）；None 表示尚未加载
_STATUS_NAMES: dict[int, str] | None = None


def _load_status_names(data_root: str | None = None) -> dict[int, str]:
    global _STATUS_NAMES
    if _STATUS_NAMES is None:
        _STATUS_NAMES = {}
        try:
            from .ini_util import load_ini
            root = Path(data_root) if data_root else Path(r"F:\seer\seer_cfg\json")
            doc = load_ini(root / "battle_effects.ini")
            for sec, kv in doc.sections:
                if sec.lstrip("-").isdigit():
                    _STATUS_NAMES[int(sec)] = kv.get("Name", "")
        except Exception:
            pass
    return _STATUS_NAMES


# 标记/场地 BUFF 的 id -> 名称（SignBuff.ini 的 dec）
_BUFF_NAMES: dict[int, str] | None = None


def _load_buff_names(data_root: str | None = None) -> dict[int, str]:
    global _BUFF_NAMES
    if _BUFF_NAMES is None:
        _BUFF_NAMES = {}
        try:
            from .ini_util import load_ini
            root = Path(data_root) if data_root else Path(r"F:\seer\seer_cfg\json")
            doc = load_ini(root / "SignBuff.ini")
            for sec, kv in doc.sections:
                if sec.lstrip("-").isdigit():
                    _BUFF_NAMES[int(sec)] = kv.get("dec", "")
        except Exception:
            pass
    return _BUFF_NAMES


def _is_catch(v: int) -> bool:
    return CATCH_LO <= v <= CATCH_HI


@dataclass(slots=True)
class PetSlot:
    species: int
    name: str
    catch_time: int
    slot: str = ""          # 首发/正式/待命

    def as_dict(self) -> dict:
        return {"species": self.species, "name": self.name,
                "catch_time": self.catch_time, "slot": self.slot}


@dataclass(slots=True)
class TurnRecord:
    turn: int
    skill_id: int | None = None
    skill_name: str = ""
    active_catch: int | None = None
    active_species: int | None = None
    active_name: str = ""
    switch_to_catch: int | None = None    # 出招后 2407 换到的 catch
    switch_to_species: int | None = None   # 换入精灵 species（若有）
    switch_to_name: str = ""               # 换入精灵名称
    switch_kind: str = ""                  # 换宠类型：active=主动(占回合) / passive=被动(死亡免费)
    enemy_hp: int | None = None
    enemy_hp_max: int | None = None
    my_hp: int | None = None
    my_hp_max: int | None = None
    my_hp_prev: int | None = None         # 我方本回合开始时的血（=上回合结算后血/开场血/换入血）
    my_hp_delta: int | None = None        # 我方结算后血 - 开始血（负数=受到伤害，正数=回复）
    damage_taken: int | None = None       # 我方本回合受到的净伤害：开始血 - 结算后血（>=0；被回复/减伤抵消时可为 0）
    damage: int | None = None             # 净伤害：敌方本回合开始时血 - 结算后血（<=0 可能被回复/减伤抵消）
    enemy_skill_id: int | None = None     # 敌方本回合使用的技能/被动
    enemy_skill_name: str = ""
    enemy_hp_prev: int | None = None      # 敌方本回合开始时的血（=上回合结算后血）
    enemy_hp_delta: int | None = None     # 敌方结算后血 - 开始血（负数=掉血，0=持平，正数=回复）
    enemy_eid: int | None = None
    is_crit: bool | None = None            # 我方本回合是否打出暴击
    enemy_is_crit: bool | None = None      # 敌方本回合是否打出暴击
    my_effect: str = ""                    # 我方技能的克制关系（无效/微弱/克制）
    enemy_effect: str = ""                 # 敌方技能的克制关系
    my_priority: int | None = None         # 我方本回合先制（>0 先手）
    enemy_priority: int | None = None      # 敌方本回合先制
    my_gain_hp: int | None = None          # 我方本回合回血（负=额外掉血）
    enemy_gain_hp: int | None = None       # 敌方本回合回血
    my_atk_times: int | None = None        # 我方技能次数（连击）
    enemy_atk_times: int | None = None     # 敌方技能次数
    my_skill_pp: list[list[int]] = field(default_factory=list)   # 我方在场精灵技能剩余 PP（[技能id, pp]）
    enemy_skill_pp: list[list[int]] = field(default_factory=list)  # 敌方技能剩余 PP
    switch_lock_catch: int | None = None   # 强制换宠被锁的 catch（0 表示无）
    team_hp: list[dict] = field(default_factory=list)     # 我方全队血量快照（含场下）
    site_buffs: list[str] = field(default_factory=list)   # 场地 BUFF（回合类效果）
    marks: list[str] = field(default_factory=list)        # 在场精灵标记 BUFF
    status: list[str] = field(default_factory=list)        # 我方本回合状态/能力变化/免疫
    enemy_status: list[str] = field(default_factory=list)  # 敌方本回合状态/能力变化/免疫

    def as_dict(self) -> dict:
        return {
            "turn": self.turn,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "active_catch": self.active_catch,
            "active_species": self.active_species,
            "active_name": self.active_name,
            "switch_to_catch": self.switch_to_catch,
            "switch_to_species": self.switch_to_species,
            "switch_to_name": self.switch_to_name,
            "switch_kind": self.switch_kind,
            "enemy_hp": self.enemy_hp,
            "enemy_hp_max": self.enemy_hp_max,
            "my_hp": self.my_hp,
            "my_hp_max": self.my_hp_max,
            "my_hp_prev": self.my_hp_prev,
            "my_hp_delta": self.my_hp_delta,
            "damage_taken": self.damage_taken,
            "damage": self.damage,
            "enemy_skill_id": self.enemy_skill_id,
            "enemy_skill_name": self.enemy_skill_name,
            "enemy_hp_prev": self.enemy_hp_prev,
            "enemy_hp_delta": self.enemy_hp_delta,
            "enemy_eid": self.enemy_eid,
            "is_crit": self.is_crit,
            "enemy_is_crit": self.enemy_is_crit,
            "my_effect": self.my_effect,
            "enemy_effect": self.enemy_effect,
            "my_priority": self.my_priority,
            "enemy_priority": self.enemy_priority,
            "my_gain_hp": self.my_gain_hp,
            "enemy_gain_hp": self.enemy_gain_hp,
            "my_atk_times": self.my_atk_times,
            "enemy_atk_times": self.enemy_atk_times,
            "my_skill_pp": [list(p) for p in self.my_skill_pp],
            "enemy_skill_pp": [list(p) for p in self.enemy_skill_pp],
            "switch_lock_catch": self.switch_lock_catch,
            "team_hp": [dict(h) for h in self.team_hp],
            "site_buffs": list(self.site_buffs),
            "marks": list(self.marks),
            "status": list(self.status),
            "enemy_status": list(self.enemy_status),
        }


@dataclass(slots=True)
class ResultRecord:
    """对战结果记录（战报的第二部分）。"""
    over: bool = False              # 是否收到 2506（战斗正常结束）
    passed: bool = False            # 是否收到 45827/42390（因子过关）
    winner: str = ""                # 胜利 / 战斗结束(未判胜负) / 未结束
    turns: int = 0                  # 总回合数
    enemy_hp: int | None = None     # 结束时敌方血
    enemy_hp_max: int | None = None
    my_hp: int | None = None        # 结束时我方当前精灵血
    my_hp_max: int | None = None
    damage_taken_total: int | None = None   # 我方累计受到的伤害（逐回合 damage_taken 之和）
    damage_dealt_total: int | None = None   # 我方累计输出伤害（逐回合 damage 之和）

    def as_dict(self) -> dict:
        return {
            "over": self.over,
            "passed": self.passed,
            "winner": self.winner,
            "turns": self.turns,
            "enemy_hp": self.enemy_hp,
            "enemy_hp_max": self.enemy_hp_max,
            "my_hp": self.my_hp,
            "my_hp_max": self.my_hp_max,
            "damage_taken_total": self.damage_taken_total,
            "damage_dealt_total": self.damage_dealt_total,
        }


@dataclass(slots=True)
class BattleReport:
    uid: int | None
    title: str = "战斗战报"
    factor_name: str = ""
    design_id: int | None = None
    stage_index: int | None = None
    enemy_name: str = ""            # 敌方精灵名（从 2504 开战帧 UTF-8 串提取，boss 自定义名才存在）
    lineup: list[PetSlot] = field(default_factory=list)
    equipment: list[dict] = field(default_factory=list)
    title_equipped: list[dict] = field(default_factory=list)
    clothes: list[dict] = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)             # 第一部分：过程（每回合）
    result: ResultRecord = field(default_factory=ResultRecord)        # 第二部分：结果
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "uid": self.uid,
            "title": self.title,
            "factor_name": self.factor_name,
            "design_id": self.design_id,
            "stage_index": self.stage_index,
            "enemy_name": self.enemy_name,
            "lineup": [p.as_dict() for p in self.lineup],
            "equipment": [dict(e) for e in self.equipment],
            "title_equipped": [dict(t) for t in self.title_equipped],
            "clothes": [dict(c) for c in self.clothes],
            "turns": [t.as_dict() for t in self.turns],
            "result": self.result.as_dict(),
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------
# 阵容（来自 read_bag）
# --------------------------------------------------------------------------
def lineup_from_bag(bag: dict, *, species_names: dict[int, str] | None = None) -> list[PetSlot]:
    names = species_names or {}
    out: list[PetSlot] = []
    formal = bag.get("正式", [])
    for i, p in enumerate(formal):
        sp = int(p["species_id"])
        out.append(PetSlot(sp, names.get(sp) or p.get("name") or str(sp),
                           int(p["catch_time"]), slot="首发" if i == 0 else "正式"))
    for p in bag.get("待命", []):
        sp = int(p["species_id"])
        out.append(PetSlot(sp, names.get(sp) or p.get("name") or str(sp),
                           int(p["catch_time"]), slot="待命"))
    return out


# --------------------------------------------------------------------------
# 装备/称号（来自 snapshot_from_live）
# --------------------------------------------------------------------------
def equip_from_snapshot(snap: dict) -> tuple[list[dict], list[dict], list[dict]]:
    equipment = []
    for e in snap.get("equipment", []):
        if e.get("bonus") or e.get("suit_bonus"):
            equipment.append({"slot": e.get("slot", ""), "name": e.get("name", ""),
                              "bonus": e.get("bonus", ""), "suit": e.get("suit", ""),
                              "suit_bonus": e.get("suit_bonus", ""), "id": e.get("id")})
    titles = [{"name": t.get("name", ""), "bonus": t.get("bonus", ""), "id": t.get("id")}
              for t in snap.get("titles", [])]
    clothes = [{"slot": c.get("slot", ""), "name": c.get("name", ""), "id": c.get("id")}
               for c in snap.get("clothes", [])]
    return equipment, titles, clothes


# --------------------------------------------------------------------------
# 血量解析（数组扫描）
# --------------------------------------------------------------------------
def _discover_enemy(frames: list[dict], my_catches: set[int]) -> tuple[int | None, int | None]:
    """从 2504/2505 里发现「敌方时刻 id + 满血」。

    规则：在 catch_time 合法区间里，找一个**不属于我方**的 id，且它后面 +4/+8 是
    「>=2000 的满血」配对（因子 boss 满血通常是 10000）。
    """
    for f in frames:
        if f["cmd"] not in (S2C_START, S2C_SKILL):
            continue
        b = bytes.fromhex(f["body"])
        for off in range(0, len(b) - 11):
            eid = struct.unpack_from(">I", b, off)[0]
            if not _is_catch(eid) or eid in my_catches:
                continue
            cur = struct.unpack_from(">I", b, off + 4)[0]
            mx = struct.unpack_from(">I", b, off + 8)[0]
            if 2000 <= mx <= 200000 and 0 <= cur <= mx:
                return int(eid), int(mx)
    return None, None


def _enemy_hp_from_body(body: bytes, enemy_max: int, exclude: set[int] | None = None) -> int | None:
    """敌方当前血：2505 里敌方血量以 [当前血][满血] 成对出现。

    排除 0 和「我方精灵的满血值」（否则会把六界 163/时空 414 等我方血量误当敌方血）。
    """
    if not body or enemy_max is None:
        return None
    exclude = exclude or set()
    b = body
    for off in range(0, len(b) - 7):
        mx = struct.unpack_from(">I", b, off + 4)[0]
        if mx != enemy_max:
            continue
        cur = struct.unpack_from(">I", b, off)[0]
        if cur <= enemy_max and cur not in exclude:
            return int(cur)
    return None


def _team_max_hp_from_2504(body: bytes, known_catches: set[int]) -> dict[int, int]:
    """从 2504 里把「catch_time -> 满血」映射出来（近似：catch 后 +8 为满血，+4 当前血）。"""
    out: dict[int, int] = {}
    for off in range(0, len(body) - 11):
        ct = struct.unpack_from(">I", body, off)[0]
        if ct not in known_catches:
            continue
        hv = struct.unpack_from(">I", body, off + 8)[0]
        hv2 = struct.unpack_from(">I", body, off + 4)[0]
        cand = hv if 1 <= hv <= 200000 else hv2
        if 1 <= cand <= 200000:
            out[ct] = int(cand)
    return out


def _starter_hp_from_2504(body: bytes, known_catches: set[int]) -> dict | None:
    """2504 开战帧的首发精灵状态：catch@0x20 / 当前血@0x24 / 满血@0x28。

    用于给第 1 回合「我方开始时的血」提供真实基准（而非一律当满血）。
    """
    if len(body) < 0x2C:
        return None
    catch = _u32(body, 0x20)
    cur = _u32(body, 0x24)
    mx = _u32(body, 0x28)
    if catch is None or (known_catches and catch not in known_catches):
        return None
    if mx is None or not (1 <= mx <= 200000):
        return None
    if cur is None or not (0 <= cur <= mx):
        return None
    return {"catch": catch, "hp": int(cur), "max_hp": int(mx)}


def _switch_ack_hp(body: bytes, known_catches: set[int]) -> dict | None:
    """2407 换宠回包：换入精灵 catch@0x08 / 当前血@0x20 / 满血@0x24。

    用于换宠后下一回合「我方开始时的血」的真实基准。
    """
    if len(body) < 0x28:
        return None
    catch = _u32(body, 0x08)
    cur = _u32(body, 0x20)
    mx = _u32(body, 0x24)
    if catch is None or (known_catches and catch not in known_catches):
        return None
    if mx is None or not (1 <= mx <= 200000):
        return None
    if cur is None or not (0 <= cur <= mx):
        return None
    return {"catch": catch, "hp": int(cur), "max_hp": int(mx)}


_CJK_RUN = re.compile(r"[\u4e00-\u9fff·]{2,16}")


def _enemy_name_from_body(body: bytes) -> str:
    """从 2504 开战帧提取敌方精灵名（boss 自定义名以 UTF-8 中文串嵌在敌方段）。

    启发式：取最长中文串。2504 只含「双方登场精灵 + 血」，我方登场精灵名由 species 本地反查、
    不内嵌，因此该帧的中文串通常是敌方（因子 boss）的自定义名。返回值可能为空串。
    """
    if not body:
        return ""
    try:
        s = body.decode("utf-8", "ignore")
    except Exception:
        return ""
    runs = _CJK_RUN.findall(s)
    if not runs:
        return ""
    return max(runs, key=len)


def _lookahead_switch_kind(timeline: list[dict], idx: int) -> str:
    """推断一次换宠是「主动(占回合)」还是「被动(死亡免费)」。

    主动换宠会在 2407 之后收到对手 2505 结算（占掉一个回合）；被动换宠只收到 2407 回包，
    直到下一次 2405 出招前都没有 2505。
    """
    for j in range(idx + 1, min(idx + 8, len(timeline))):
        e = timeline[j]
        if e.get("dir") == "c2s" and e.get("cmd") == C2S_SKILL:
            return "passive"
        if e.get("dir") == "s2c" and e.get("cmd") == S2C_SKILL:
            return "active"
    return "passive"


def _my_hp_from_body(body: bytes, catch: int, max_hp: int | None) -> tuple[int | None, int | None]:
    """我方某 catch 的当前血/满血（best-effort）：定位 catch 后，向后找 [cur][max] 对。"""
    if not body or catch is None:
        return None, None
    b = body
    ct = catch & 0xFFFFFFFF
    targets = [max_hp] if max_hp else []
    for off in range(0, len(b) - 7):
        v = struct.unpack_from(">I", b, off)[0]
        if v != ct:
            continue
        # catch 后面 32 字节内找 [cur][max] 对
        for k in range(4, 33, 4):
            p = off + k
            if p + 8 > len(b):
                break
            cur = struct.unpack_from(">I", b, p)[0]
            mx = struct.unpack_from(">I", b, p + 4)[0]
            if 1 <= cur <= 200000 and 1 <= mx <= 200000 and (not targets or mx in targets):
                return int(cur), int(mx)
    return None, None


def _settle_records(body: bytes, *, my_catches: set[int] | None = None) -> list[dict]:
    """2505 结算帧里的「动作块」扫描。

     动作块布局（每块 11×u32，id 落在 catch 区间 = 我方 catch 或敌方 eid）：
       [+0] 判别：0=敌方动作块 / uid=我方动作块
       [+1] skill_id（该方本回合使用的技能/被动）
       [+2] 回合序号
       [+3] id（我方 catch_time 或敌方 eid）
       [+4] flag  [+5] 1  [+6] x  [+7] 0  [+8] 0
       [+9] 当前血  [+10] 满血
     仅保留「满血合理、当前血 ≤ 满血」的记录；别名/占位块（血 0/微小）不在此列。
    """
    my_catches = my_catches or set()
    out: list[dict] = []
    for off in range(0, len(body) - 40):
        idv = _u32(body, off)
        if not _is_catch(idv):
            continue
        cur = _u32(body, off + 24)
        mx = _u32(body, off + 28)
        if mx is None or not (1 <= mx <= 200000):
            continue
        if cur is None or cur > mx:
            continue
        out.append({
            "off": off,
            "role": "my" if idv in my_catches else "enemy",
            "id": idv,
            "skill_id": _u32(body, off - 8) if off >= 8 else None,
            "turn": _u32(body, off - 4) if off >= 4 else None,
            "hp": cur,
            "max_hp": mx,
        })
    return out


def _enemy_head_block(body: bytes, my_catches: set[int] | None = None,
                      enemy_max: int | None = None) -> dict | None:
    """2505 头部固定「敌方动作块」：byte0=0 时落在 12(敌方eid)/4(技能)/36(血)/40(满血)。"""
    my_catches = my_catches or set()
    if len(body) < 44:
        return None
    eid = _u32(body, 12)
    skill = _u32(body, 4)
    hp = _u32(body, 36)
    mx = _u32(body, 40)
    if not (_is_catch(eid) and eid not in my_catches and mx and 1 <= mx <= 200000):
        return None
    if hp is None or hp > mx:
        return None
    if enemy_max is not None and mx != enemy_max:
        return None
    return {"id": eid, "skill_id": skill, "hp": hp, "max_hp": mx}


def _discover_enemy_from_2505(body: bytes, my_catches: set[int] | None = None) -> tuple[int | None, int | None]:
    """从第一个 2505 的头部敌方块发现「敌方 eid + 满血」（比 2504 扫描稳，避免误判）。"""
    b = _enemy_head_block(body, my_catches)
    if b:
        return int(b["id"]), int(b["max_hp"])
    for r in _settle_records(body, my_catches=my_catches):
        if r["role"] == "enemy" and r["max_hp"] and r["max_hp"] >= 2000:
            return int(r["id"]), int(r["max_hp"])
    return None, None


def _enemy_max_hp_from_frames(frames: list[dict], my_catches: set[int] | None = None) -> int | None:
    """从帧列表里发现敌方满血（2505 头部敌方块优先，2504 扫描兜底）。

    历史上该函数被调用却没有定义，导致 offline 验证脚本 ImportError；此处补回。
    """
    known = my_catches or set()
    for f in frames:
        if f.get("cmd") != S2C_SKILL:
            continue
        eid, emax = _discover_enemy_from_2505(bytes.fromhex(f["body"]), known)
        if emax:
            return int(emax)
    eid, emax = _discover_enemy(frames, known)
    return int(emax) if emax else None


def _enemy_action_by_eid(body: bytes, enemy_eid: int | None, enemy_max: int | None) -> dict | None:
    """按「敌方 eid」在 2505 里精确定位敌方动作块（比按“非我方 catch”判定稳，不依赖阵容完整性）。

    敌方动作块布局与头块一致：``[skill@eid-8][turn@eid-4][eid][…][cur@eid+24][max@eid+28]``。
    敌方阵亡时该块 ``max`` 会塌成 0，这时用已知 ``enemy_max`` 兜底展示满血（避免把 39 之类
    误判成敌方满血）。返回 ``{id, skill_id, turn, hp, max_hp}``，找不到返回 None。
    """
    if not body or enemy_eid is None:
        return None
    eid = enemy_eid & 0xFFFFFFFF
    for off in range(8, len(body) - 28):
        if _u32(body, off) != eid:
            continue
        cur = _u32(body, off + 24)
        if cur is None or cur < 0:
            continue
        skill = _u32(body, off - 8)
        turn = _u32(body, off - 4)
        mx = _u32(body, off + 28)
        show_mx = mx if (mx is not None and mx == enemy_max) else enemy_max
        return {"id": eid, "skill_id": skill, "turn": turn, "hp": int(cur), "max_hp": show_mx, "off": off}
    return None


def _my_action_by_catch(body: bytes, catch: int | None, turn: int | None,
                        known_max: int | None = None) -> dict | None:
    """按「我方 catch + 回合号」在 2505 里精确定位我方动作块（与 _enemy_action_by_eid 对称）。

    用 turn 过滤是为了避开同一 catch 在队尾「阵容快照」里的另一个出现（那边没有 [skill/turn]
    前缀，cur/max 偏移也不同）。我方阵亡时动作块 ``max`` 会塌成 0，此时用 ``known_max`` 兜底。
    返回 ``{id, skill_id, turn, hp, max_hp}``，找不到返回 None。
    """
    if not body or catch is None:
        return None
    ct = catch & 0xFFFFFFFF
    for off in range(8, len(body) - 28):
        if _u32(body, off) != ct:
            continue
        # 动作块签名：off-8 是技能（阵容快照里该位置为 0）；另有 off-4 为回合号
        skill = _u32(body, off - 8)
        if skill in (None, 0):
            continue
        if turn is not None and _u32(body, off - 4) != turn:
            continue
        cur = _u32(body, off + 24)
        if cur is None or cur < 0:
            continue
        turn_at = _u32(body, off - 4)
        mx = _u32(body, off + 28)
        show_mx = mx if (mx is not None and 1 <= mx <= 200000) else known_max
        return {"id": ct, "skill_id": skill, "turn": turn_at, "hp": int(cur), "max_hp": show_mx, "off": off}
    return None


def _action_block_off(body: bytes, idv: int | None, turn: int | None = None) -> int | None:
    """在 2505 里定位 id（我方 catch / 敌方 eid）的动作块 offset（返回 id 所在 offset）。"""
    if not body or idv is None:
        return None
    iv = idv & 0xFFFFFFFF
    for off in range(8, len(body) - 52):
        if _u32(body, off) != iv:
            continue
        if _u32(body, off - 8) in (None, 0):
            continue
        if turn is not None and _u32(body, off - 4) != turn:
            continue
        return off
    return None


def _read_action_extras(body: bytes, off: int | None) -> dict:
    """按 AttackValue.as 的解码顺序完整走一遍动作块，抽取战报需要的关键字段。

    固定头 13×u32，之后依次：技能列表(含 PP)、isCrit、特效状态字节、specailArr、
    sideEffects、battle_lv/change_bitset/priority、immunizationStates、changehps、
    requireSwitchCthTime、maxHpSelf/maxHpOther/secretLaw、skillRunawayMarks、
    siteBuffInfo×2、markBuffInfo、signInfoHash、lockedSkillArr、skillResultArr、
    最后 zhuijiId/zhuijiHurt/btlElemtype/transformId。
    """
    if not body or off is None:
        return {}
    p = off - 12
    if p < 0 or p + 52 > len(body):
        return {}
    effect = _u32(body, p + 16)      # 1=无效 2=微弱 3=克制
    atk = _u32(body, p + 20)         # 技能次数/连击
    lost = _u32(body, p + 24)        # 对方掉血（结算前原始伤害）
    real = _u32(body, p + 28)        # 真实伤害
    gain = _s32(body, p + 32)        # 自己回血
    q = p + 52
    nsk = _u32(body, q)
    if nsk is None or nsk > 40:
        return {}
    skill_pp = [(_u32(body, q + 4 + i * 8), _u32(body, q + 8 + i * 8)) for i in range(nsk)]
    q += 4 + nsk * 8
    crit = _u32(body, q)
    q += 4
    nst = _u8(body, q)
    if nst is None or nst > 64:
        return {}
    q += 1 + nst
    nsp = _u32(body, q)
    if nsp is None or nsp > 64:
        return {}
    q += 4 + nsp * 4
    nside = _u32(body, q)
    if nside is None or nside > 32:
        return {}
    q += 4
    sides = [(_u32(body, q + i * 12), _u32(body, q + i * 12 + 4), _u32(body, q + i * 12 + 8))
             for i in range(nside)]
    q += nside * 12
    blv = _s32(body, q)
    q += 4
    cb = _u32(body, q)
    q += 4
    pri = _u32(body, q)
    q += 4
    nimm = _u32(body, q)
    if nimm is None or nimm > 64:
        return {}
    imm = [(_u32(body, q + 4 + i * 4) or 0) for i in range(nimm)]
    q += 4 + nimm * 4
    nch = _u32(body, q)
    if nch is None or nch > 20:
        return {}
    q += 4
    changehps = []
    for _ in range(nch):
        pid = _u32(body, q)
        hp = _u32(body, q + 4)
        mx = _u32(body, q + 8)
        lock = _u32(body, q + 12)
        cjn = _u32(body, q + 16)
        cjr = _u32(body, q + 20)
        q += 24
        nmk = _u8(body, q)
        if nmk is None or nmk > 64:
            return {}
        q += 1
        pmarks = []
        for _ in range(nmk):
            mid = _u16(body, q)
            mnum = _u8(body, q + 2)
            q += 3
            pmarks.append([mid, mnum])
        changehps.append({"catch": pid, "hp": hp, "max_hp": mx, "lock": lock,
                          "chujue_number": cjn, "chujue_round": cjr, "marks": pmarks})
    switch_cth = _u32(body, q)
    q += 12  # requireSwitchCthTime + maxHpSelf + maxHpOther
    secret = _u32(body, q)
    q += 4
    nrun = _u32(body, q)
    if nrun is None or nrun > 64:
        return {}
    q += 4 + nrun * 4
    site1 = (_u16(body, q), _u8(body, q + 2))
    q += 3
    site2 = (_u16(body, q), _u8(body, q + 2))
    q += 3
    nmk2 = _u8(body, q)
    if nmk2 is None or nmk2 > 64:
        return {}
    q += 1
    marks = []
    for _ in range(nmk2):
        mid = _u16(body, q)
        mnum = _u8(body, q + 2)
        q += 3
        marks.append([mid, mnum])
    nsign = _u32(body, q)
    if nsign is None or nsign > 64:
        return {}
    q += 4
    signs = []
    for _ in range(nsign):
        v1 = _u32(body, q)
        v2 = _u32(body, q + 4)
        q += 8
        signs.append({"id": (v1 & 0xFFFF), "lv": ((v1 >> 16) & 0xFF),
                      "round": ((v1 >> 24) & 0xFF), "sp": v2})
    q += 20  # lockedSkillArr（5×u32）
    nres = _u32(body, q)
    if nres is None or nres > 64:
        return {}
    q += 4 + nres * 4
    q += 8  # zhuijiId + zhuijiHurt
    q += 4  # btlElemtype
    transform = _u32(body, q) if q + 4 <= len(body) else None
    immunized = any((v & 0x0F) in (9, 1) for v in imm)
    return {"is_crit": crit == 1, "sides": sides, "battle_lv": blv,
            "change_bitset": cb, "priority": pri, "effect": effect, "atk_times": atk,
            "lost_hp": lost, "real_hurt": real, "gain_hp": gain, "skill_pp": skill_pp,
            "immunized": immunized, "require_switch_cth": switch_cth, "transform_id": transform,
            "secret_law": secret, "changehps": changehps,
            "site_buffs": [site1, site2], "mark_buffs": marks, "signs": signs}


def _format_status_effects(sides: list, status_names: dict[int, str]) -> list[str]:
    """把 (type,id,parm) 状态列表渲染成可读文本：异常状态 / 能力变化 / 标记。"""
    out: list[str] = []
    for t, i, parm in sides:
        if t == 0:   # ABNORMAL 异常状态
            nm = status_names.get(i) or f"异常#{i}"
            if i == 11 and 1 <= parm <= 5:
                nm = f"衰弱{['25%', '50%', '100%', '250%', '500%'][parm - 1]}"
            elif i == 15 and parm:
                nm = f"冰封({parm}回合)"
            elif i in (17, 18):
                pass  # 免疫：名字本身已说明，不追加持续回合
            elif parm:
                nm = f"{nm}({parm}回合)"
            out.append(nm)
        elif t == 1:  # TRAIT 能力变化
            nm = _ABILITY_NAMES[i] if 0 <= i < len(_ABILITY_NAMES) else f"能力#{i}"
            lv = (parm or 0) - 6
            out.append(f"{nm}{lv:+d}")
        elif t == 2:  # STAMP 标记
            out.append(f"标记#{i}")
        else:
            out.append(f"效果{t}#{i}")
    return out


def _buff_label(names: dict[int, str], bid: int, amt: int | None, *, is_mark: bool = False) -> str:
    """把场地/标记 BUFF 渲染成文本：名称(回合) / 名称×层数。"""
    nm = names.get(bid) or f"buff#{bid}"
    if amt and amt != 1:
        return f"{nm}×{amt}" if is_mark else f"{nm}({amt}回合)"
    return nm


# --------------------------------------------------------------------------
# 出招序列（C2S 命令日志）
# --------------------------------------------------------------------------
def turns_from_c2s(c2s_log: list[dict], *, skill_names: dict[int, str] | None = None,
                   catches: dict[int, tuple[int, str]] | None = None) -> list[TurnRecord]:
    """c2s_log: [{'cmd': 2404/2405/2407, 'body': hex}, ...]"""
    names = skill_names or {}
    catch_map = catches or {}   # catch -> (species, name)
    turns: list[TurnRecord] = []
    turn = 0
    active_catch: int | None = None
    for c in c2s_log:
        cmd = c["cmd"]
        body = bytes.fromhex(c["body"]) if c.get("body") else b""
        if cmd == C2S_SKILL:
            turn += 1
            skill_id = struct.unpack_from(">I", body, 0)[0] if len(body) >= 4 else None
            rec = TurnRecord(turn=turn, skill_id=skill_id, skill_name=names.get(skill_id, ""),
                             active_catch=active_catch)
            if active_catch is not None and active_catch in catch_map:
                rec.active_species, rec.active_name = catch_map[active_catch]
            turns.append(rec)
        elif cmd == C2S_SWITCH:
            ct = struct.unpack_from(">I", body, 0)[0] if len(body) >= 4 else None
            active_catch = ct & 0xFFFFFFFF
            if turns:
                turns[-1].switch_to_catch = active_catch
    return turns


def _load_names(data_root: str | None) -> tuple[dict[int, str], dict[int, str]]:
    if not data_root:
        return {}, {}
    try:
        from .battle_data import BattleData
        data = BattleData(data_root)
        skill_names = {sid: m.name for sid, m in data.moves.items()}
        species_names = {sid: s.name for sid, s in data.species.items()}
        return skill_names, species_names
    except Exception:
        return {}, {}


def build_report_from_timeline(
    timeline: list[dict],
    *,
    bag: dict | None = None,
    snap: dict | None = None,
    skill_names: dict[int, str] | None = None,
    species_names: dict[int, str] | None = None,
    data_root: str | None = None,
    factor_name: str = "",
    design_id: int | None = None,
    stage_index: int | None = None,
    enemy_max_hp: int | None = None,
    resolve_skill: Any = None,
) -> BattleReport:
    """从「单场战斗的按时间顺序 C2S/S2C 事件列表」生成战报。

    timeline 每项：{'dir':'c2s'|'s2c', 'cmd':int, 'body':hex字符串, 'result':int(可选)}
    """
    # 统一方向字段：驱动层(battle_driver/factor_runner)写 send/recv，旧文档写 c2s/s2c。
    timeline = [
        {**e, "dir": "c2s" if e.get("dir") == "send" else ("s2c" if e.get("dir") == "recv" else e.get("dir"))}
        for e in timeline
    ]
    sk_names, sp_names = _load_names(data_root)
    st_names = _load_status_names(data_root)
    buff_names = _load_buff_names(data_root)
    if skill_names:
        sk_names = {**sk_names, **skill_names}
    if species_names:
        sp_names = {**sp_names, **species_names}

    uid = (bag or {}).get("uid")
    rep = BattleReport(uid=uid, factor_name=factor_name, design_id=design_id, stage_index=stage_index)
    catches: dict[int, tuple[int, str]] = {}
    if bag:
        rep.lineup = lineup_from_bag(bag, species_names=sp_names)
        for p in rep.lineup:
            catches[p.catch_time] = (p.species, p.name)
    if snap:
        rep.equipment, rep.title_equipped, rep.clothes = equip_from_snapshot(snap)

    # 首发 catch（若已知阵容）
    starter_catch: int | None = None
    if rep.lineup:
        for p in rep.lineup:
            if p.slot == "首发":
                starter_catch = p.catch_time
                break

    # 技能名兜底：本地库缺的（尤其 BOSS 被动/专属技）尝试在线反查
    _resolved: dict[int, str] = {}

    def _skill_name(sid: int | None) -> str:
        if sid is None:
            return ""
        n = sk_names.get(sid)
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

    # 先把 S2C 帧抽出来 → 我方满血映射 + 开场首发血 + 敌方满血
    s2c = [e for e in timeline if e.get("dir") == "s2c"]
    my_max: dict[int, int] = {}
    known = set(catches)
    starter_from_2504: dict | None = None
    for e in s2c:
        if e["cmd"] == S2C_START:
            body2504 = bytes.fromhex(e["body"])
            my_max = _team_max_hp_from_2504(body2504, known)
            starter_from_2504 = _starter_hp_from_2504(body2504, known)
            rep.enemy_name = _enemy_name_from_body(body2504)
            break
    if starter_from_2504 is not None:
        if starter_from_2504["max_hp"]:
            my_max.setdefault(starter_from_2504["catch"], starter_from_2504["max_hp"])
        if starter_catch is None:
            starter_catch = starter_from_2504["catch"]

    # 敌方满血：优先从 2505 头部敌方块读（最稳），2504 扫描兜底
    enemy_eid: int | None = None
    discovered_max: int | None = None
    for e in s2c:
        if e["cmd"] == S2C_SKILL:
            enemy_eid, discovered_max = _discover_enemy_from_2505(bytes.fromhex(e["body"]), known)
            if discovered_max:
                break
    if discovered_max is None:
        enemy_eid, discovered_max = _discover_enemy(s2c, known)
    if enemy_max_hp is None:
        enemy_max_hp = discovered_max
    if enemy_max_hp:
        src = "传入" if enemy_max_hp != discovered_max else "自帧发现"
        rep.notes.append(f"敌方满血={enemy_max_hp}（{src}）")

    # 逐事件走时间线：敌方血/技能在 2505 结算帧即时落地（末回合也能结清）
    active_catch = starter_catch
    turn = 0
    cur: TurnRecord | None = None
    prev_enemy_hp: int | None = enemy_max_hp  # 开战满血，供第 1 回合算净伤害
    # 我方每只精灵「上一结算后的血」：用于算「我方受到的伤害」。开场以 2504 首发血为基准。
    me_seen: dict[int, int | None] = {}
    if starter_from_2504 is not None:
        me_seen[starter_from_2504["catch"]] = starter_from_2504["hp"]

    for i, e in enumerate(timeline):
        cmd = e.get("cmd")
        d = e.get("dir")
        body = bytes.fromhex(e["body"]) if e.get("body") else b""
        if d == "c2s":
            if cmd == C2S_SKILL:
                turn += 1
                sid = struct.unpack_from(">I", body, 0)[0] if len(body) >= 4 else None
                cur = TurnRecord(turn=turn, skill_id=sid, skill_name=_skill_name(sid), active_catch=active_catch)
                if active_catch is not None and active_catch in catches:
                    cur.active_species, cur.active_name = catches[active_catch]
                cur.enemy_hp_max = enemy_max_hp
                cur.enemy_hp_prev = prev_enemy_hp
                cur.enemy_eid = enemy_eid
                cur.my_hp_max = my_max.get(active_catch) if active_catch else None
                cur.my_hp_prev = me_seen.get(active_catch)
                rep.turns.append(cur)
            elif cmd == C2S_SWITCH and len(body) >= 4:
                new_catch = struct.unpack_from(">I", body, 0)[0] & 0xFFFFFFFF
                if cur is not None:
                    cur.switch_to_catch = new_catch
                    if new_catch in catches:
                        cur.switch_to_species, cur.switch_to_name = catches[new_catch]
                    cur.switch_kind = _lookahead_switch_kind(timeline, i)
                active_catch = new_catch
                # 换入精灵「开始血」先按满血兜底，2407 回包到达后会被真实值覆盖
                me_seen.setdefault(active_catch, my_max.get(active_catch))
        elif d == "s2c" and cur is not None:
            if cmd == S2C_SKILL:
                en = _enemy_action_by_eid(body, enemy_eid, enemy_max_hp)
                if en is None:
                    en = _enemy_head_block(body, known)
                if en is None:
                    for r in _settle_records(body, my_catches=known):
                        if r["role"] == "enemy":
                            en = r
                            break
                if en is not None:
                    if enemy_max_hp is None:
                        enemy_max_hp = en["max_hp"]
                        enemy_eid = en["id"]
                    cur.enemy_hp = en["hp"]
                    cur.enemy_hp_max = en["max_hp"]
                    cur.enemy_skill_id = en["skill_id"]
                    cur.enemy_skill_name = _skill_name(en["skill_id"])
                    cur.enemy_eid = en["id"]
                    if cur.enemy_hp_prev is None:
                        cur.enemy_hp_prev = enemy_max_hp
                    prev = cur.enemy_hp_prev
                    cur.damage = max(0, prev - en["hp"]) if prev is not None else None
                    cur.enemy_hp_delta = (en["hp"] - prev) if prev is not None else None
                    prev_enemy_hp = en["hp"]
                    ex = _read_action_extras(body, en["off"])
                    if ex:
                        cur.enemy_is_crit = ex["is_crit"]
                        cur.enemy_status = _format_status_effects(ex["sides"], st_names)
                        if ex.get("immunized"):
                            cur.enemy_status.append("免疫")
                        # 变身/换技能：展示技能用 transform_id（displaySkillId）
                        if ex.get("transform_id"):
                            cur.enemy_skill_id = ex["transform_id"]
                            cur.enemy_skill_name = _skill_name(ex["transform_id"])
                        cur.enemy_skill_pp = [[s, pp or 0] for s, pp in ex.get("skill_pp", [])]
                        cur.enemy_effect = _EFFECT_NAMES.get(ex["effect"], "")
                        cur.enemy_priority = ex.get("priority") or None
                        cur.enemy_gain_hp = ex.get("gain_hp") or None
                        cur.enemy_atk_times = ex.get("atk_times") if (ex.get("atk_times") or 1) > 1 else None
                if cur.active_catch is not None:
                    mya = _my_action_by_catch(body, cur.active_catch, cur.turn,
                                               my_max.get(cur.active_catch))
                    if mya is not None:
                        cur.my_hp = mya["hp"]
                        if mya["max_hp"]:
                            cur.my_hp_max = mya["max_hp"]
                        ex = _read_action_extras(body, mya["off"])
                        if ex:
                            cur.is_crit = ex["is_crit"]
                            cur.status = _format_status_effects(ex["sides"], st_names)
                            if ex.get("immunized"):
                                cur.status.append("免疫")
                            if ex.get("transform_id"):
                                cur.skill_id = ex["transform_id"]
                                cur.skill_name = _skill_name(ex["transform_id"])
                            cur.my_skill_pp = [[s, pp or 0] for s, pp in ex.get("skill_pp", [])]
                            cur.switch_lock_catch = ex.get("require_switch_cth") or None
                            cur.my_effect = _EFFECT_NAMES.get(ex["effect"], "")
                            cur.my_priority = ex.get("priority") or None
                            cur.my_gain_hp = ex.get("gain_hp") or None
                            cur.my_atk_times = ex.get("atk_times") if (ex.get("atk_times") or 1) > 1 else None
                            cur.team_hp = [{"catch": h["catch"], "hp": h["hp"], "max_hp": h["max_hp"], "lock": h["lock"]}
                                           for h in ex.get("changehps", [])]
                            cur.site_buffs = [_buff_label(buff_names, sid, turn)
                                              for sid, turn in ex.get("site_buffs", []) if sid]
                            cur.marks = [_buff_label(buff_names, mid, num, is_mark=True)
                                         for mid, num in ex.get("mark_buffs", [])]
                    # 我方受到的伤害 = 本回合开始血 - 结算后血（负值→受到的伤害，正值→回复）
                    prev_me = cur.my_hp_prev if cur.my_hp_prev is not None else me_seen.get(cur.active_catch)
                    if cur.my_hp is not None and prev_me is not None:
                        cur.my_hp_delta = cur.my_hp - prev_me
                        cur.damage_taken = max(0, prev_me - cur.my_hp)
                    if cur.my_hp is not None:
                        me_seen[cur.active_catch] = cur.my_hp
            elif cmd == C2S_SWITCH:
                ack = _switch_ack_hp(body, known)
                if ack is not None:
                    if ack["max_hp"]:
                        my_max[ack["catch"]] = ack["max_hp"]
                    me_seen[ack["catch"]] = ack["hp"]
            elif cmd == S2C_OVER:
                rep.result.over = True
            elif cmd == S2C_WIN:
                # 42390 只是「战斗结束」，胜利/战败都会发，不代表过关
                rep.result.over = True
            elif cmd == S2C_PROGRESS:
                # 45827 才是因子过关推送
                rep.result.passed = True
                rep.result.winner = "胜利"

    # 第二部分：结果汇总
    rep.result.turns = len(rep.turns)
    _taken = [t.damage_taken for t in rep.turns if t.damage_taken is not None]
    if _taken:
        rep.result.damage_taken_total = sum(_taken)
    _dealt = [t.damage for t in rep.turns if t.damage is not None]
    if _dealt:
        rep.result.damage_dealt_total = sum(_dealt)
    if rep.turns:
        last = rep.turns[-1]
        rep.result.enemy_hp = last.enemy_hp
        rep.result.enemy_hp_max = last.enemy_hp_max or enemy_max_hp
        rep.result.my_hp = last.my_hp
        rep.result.my_hp_max = last.my_hp_max
        if last.enemy_hp == 0:      # 敌方结算后 0 血 = 已击败（过关）
            rep.result.passed = True
            rep.result.winner = "胜利"
    if not rep.result.winner:
        rep.result.winner = "未结束" if not rep.result.over else "未过关"

    return rep


# --------------------------------------------------------------------------
# 汇总（简化：不填逐回合血量，仅阵容/装备/出招；完整版用 build_report_from_timeline）
# --------------------------------------------------------------------------
def build_report(
    *,
    bag: dict | None = None,
    snap: dict | None = None,
    s2c_frames: list[dict] | None = None,
    c2s_log: list[dict] | None = None,
    skill_names: dict[int, str] | None = None,
    species_names: dict[int, str] | None = None,
    factor_name: str = "",
    design_id: int | None = None,
    stage_index: int | None = None,
) -> BattleReport:
    uid = (bag or {}).get("uid")
    rep = BattleReport(uid=uid, factor_name=factor_name, design_id=design_id, stage_index=stage_index)
    lineup: list[PetSlot] = []
    catches: dict[int, tuple[int, str]] = {}
    if bag:
        lineup = lineup_from_bag(bag, species_names=species_names)
        rep.lineup = lineup
        for p in lineup:
            catches[p.catch_time] = (p.species, p.name)
    if snap:
        equip, titles, clothes = equip_from_snapshot(snap)
        rep.equipment, rep.title_equipped, rep.clothes = equip, titles, clothes

    frames = s2c_frames or []
    c2s = c2s_log or []
    rep.turns = turns_from_c2s(c2s, skill_names=skill_names, catches=catches)

    if frames:
        # 我方满血映射（用 2504）
        known = set(catches) or {t.switch_to_catch for t in rep.turns if t.switch_to_catch}
        known = {t.active_catch for t in rep.turns if t.active_catch} | known
        known.discard(None)
        enemy_max = _enemy_max_hp_from_frames(frames)
        my_max: dict[int, int] = {}
        for f in frames:
            if f["cmd"] == S2C_START:
                my_max = _team_max_hp_from_2504(bytes.fromhex(f["body"]), known)
                break
        if enemy_max:
            rep.notes.append(f"敌方满血(自帧发现)={enemy_max}")
        # 逐回合补血量：每个 2405 后的第一个 2505，取敌方血与我方当前精灵血
        for t in rep.turns:
            t.enemy_hp_max = enemy_max
            t.my_hp_max = my_max.get(t.active_catch) if t.active_catch else None

    rep.result.turns = len(rep.turns)
    if rep.turns:
        last = rep.turns[-1]
        rep.result.enemy_hp = last.enemy_hp
        rep.result.enemy_hp_max = last.enemy_hp_max
        rep.result.my_hp = last.my_hp
        rep.result.my_hp_max = last.my_hp_max

    return rep


def report_to_text(rep: BattleReport) -> str:
    L: list[str] = []
    L.append(f"【{rep.title}】")
    if rep.factor_name:
        extra = f" design={rep.design_id}" if rep.design_id is not None else ""
        stage = f" 第{rep.stage_index}关" if rep.stage_index is not None else ""
        L.append(f"因子：{rep.factor_name}{stage}{extra}")
    if rep.enemy_name:
        L.append(f"敌方：{rep.enemy_name}")
    if rep.uid is not None:
        L.append(f"UID：{rep.uid}")
    L.append("")
    L.append("【阵容】")
    for p in rep.lineup:
        mark = "★首发" if p.slot == "首发" else p.slot
        L.append(f"  {mark} {p.name}（species={p.species} catch=0x{p.catch_time:08x}）")
    if rep.equipment:
        L.append("")
        L.append("【装备】")
        for e in rep.equipment:
            suit = f"（套装：{e['suit']}）" if e.get("suit") else ""
            bonus = f" → {e['bonus']}" if e.get("bonus") else ""
            sb = f" 套装效果:{e['suit_bonus']}" if e.get("suit_bonus") else ""
            L.append(f"  [{e['slot']}] {e['name']}{suit}{bonus}{sb}")
    if rep.title_equipped:
        L.append("")
        L.append("【称号】")
        for t in rep.title_equipped:
            L.append(f"  {t['name']}（{t['bonus']}）")
    L.append("")
    L.append("【过程 · 每回合】")
    if not rep.turns:
        L.append("  （无出招记录）")
    for t in rep.turns:
        who = t.active_name or (f"species={t.active_species}" if t.active_species else "?")
        sk = t.skill_name or (f"技能id={t.skill_id}" if t.skill_id else "?")
        if t.switch_to_catch:
            sw_name = t.switch_to_name or (f"species={t.switch_to_species}" if t.switch_to_species else f"0x{t.switch_to_catch:08x}")
            sw_kind = {"active": "主动(占回合)", "passive": "被动(死亡免费)"}.get(t.switch_kind, "")
            sw = f" → 换宠 {sw_name}{('·' + sw_kind) if sw_kind else ''}"
        else:
            sw = ""
        esk = t.enemy_skill_name or (f"技能id={t.enemy_skill_id}" if t.enemy_skill_id is not None else "")
        enemy = f"敌血 {t.enemy_hp}/{t.enemy_hp_max}" if t.enemy_hp is not None else ""
        my_prev = f"{t.my_hp_prev}→" if t.my_hp_prev is not None else ""
        my = f"我血 {my_prev}{t.my_hp}/{t.my_hp_max}" if t.my_hp is not None else ""
        dmg = f" 伤害~{t.damage}" if t.damage is not None else ""
        edelta = f" 敌血变化{t.enemy_hp_delta:+d}" if t.enemy_hp_delta is not None else ""
        mydelta = f" 我受伤{t.damage_taken}" if t.damage_taken is not None else ""
        mydelta += f"/变化{t.my_hp_delta:+d}" if t.my_hp_delta is not None else ""
        eact = f" 敌用:{esk}" if esk else ""
        ecrit = "【暴击】" if t.enemy_is_crit else ""
        mycrit = "【暴击】" if t.is_crit else ""
        myeff = f" {t.my_effect}" if t.my_effect else ""
        eeff = f" {t.enemy_effect}" if t.enemy_effect else ""
        mypri = f" 先制{t.my_priority:+d}" if t.my_priority else ""
        epri = f" 敌先制{t.enemy_priority:+d}" if t.enemy_priority else ""
        mygain = f" 回血{t.my_gain_hp}" if t.my_gain_hp else ""
        egain = f" 敌回血{t.enemy_gain_hp}" if t.enemy_gain_hp else ""
        mytimes = f"×{t.my_atk_times}" if t.my_atk_times else ""
        etimes = f"敌×{t.enemy_atk_times}" if t.enemy_atk_times else ""
        estatus = f" 敌状态[{','.join(t.enemy_status)}]" if t.enemy_status else ""
        status = f" 我状态[{','.join(t.status)}]" if t.status else ""
        mypp = next((str(pp) for s, pp in t.my_skill_pp if s == t.skill_id), None)
        mypp_s = f" PP{mypp}" if mypp is not None else ""
        epp = next((str(pp) for s, pp in t.enemy_skill_pp if s == t.enemy_skill_id), None)
        epp_s = f" 敌PP{epp}" if epp is not None else ""
        lock_s = f" 被锁换0x{t.switch_lock_catch:08x}" if t.switch_lock_catch else ""
        team_t = ""
        if t.team_hp:
            nm = {p.catch_time: (p.name or str(p.species)) for p in rep.lineup}
            cells = []
            for h in t.team_hp:
                if h.get("catch") == t.active_catch:
                    continue
                n = nm.get(h.get("catch"), f"0x{(h.get('catch') or 0):08x}")
                cells.append(f"{n}{h.get('hp')}/{h.get('max_hp')}")
            if cells:
                team_t = " 队友[" + " ".join(cells) + "]"
        site_t = f" 场地[{','.join(t.site_buffs)}]" if t.site_buffs else ""
        marks_t = f" 标记[{','.join(t.marks)}]" if t.marks else ""
        L.append(f"  第{t.turn}回合 [{who}] {sk}{mycrit}{myeff}{mytimes}{mypri}{mypp_s}{sw}"
                 f"{eact}{ecrit}{eeff}{etimes}{epri}{epp_s}  {enemy}{edelta}{egain}  "
                 f"{my}{dmg}{mydelta}{mygain}{status}{estatus}{lock_s}{team_t}{site_t}{marks_t}")
    L.append("")
    L.append("【结果】")
    r = rep.result
    L.append(f"  胜败：{r.winner or '未结束'}   结束(2506)={'是' if r.over else '否'}   过关(45827)={'是' if r.passed else '否'}")
    L.append(f"  总回合：{r.turns}")
    if r.enemy_hp is not None:
        L.append(f"  结束时敌血 {r.enemy_hp}/{r.enemy_hp_max or '?'}")
    if r.my_hp is not None:
        L.append(f"  结束时我血 {r.my_hp}/{r.my_hp_max or '?'}")
    if r.damage_taken_total is not None:
        L.append(f"  我方累计受伤 {r.damage_taken_total}")
    if r.damage_dealt_total is not None:
        L.append(f"  我方累计输出 {r.damage_dealt_total}")
    if rep.notes:
        L.append("")
        L.append("【说明】")
        for n in rep.notes:
            L.append(f"  - {n}")
    return "\n".join(L)