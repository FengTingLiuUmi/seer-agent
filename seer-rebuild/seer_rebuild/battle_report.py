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
    enemy_hp: int | None = None
    enemy_hp_max: int | None = None
    my_hp: int | None = None
    my_hp_max: int | None = None
    damage: int | None = None             # 净伤害：敌方本回合开始时血 - 结算后血（<=0 可能被回复/减伤抵消）
    enemy_skill_id: int | None = None     # 敌方本回合使用的技能/被动
    enemy_skill_name: str = ""
    enemy_hp_prev: int | None = None      # 敌方本回合开始时的血（=上回合结算后血）
    enemy_hp_delta: int | None = None     # 敌方结算后血 - 开始血（负数=掉血，0=持平，正数=回复）
    enemy_eid: int | None = None
    status: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "turn": self.turn,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "active_catch": self.active_catch,
            "active_species": self.active_species,
            "active_name": self.active_name,
            "switch_to_catch": self.switch_to_catch,
            "enemy_hp": self.enemy_hp,
            "enemy_hp_max": self.enemy_hp_max,
            "my_hp": self.my_hp,
            "my_hp_max": self.my_hp_max,
            "damage": self.damage,
            "enemy_skill_id": self.enemy_skill_id,
            "enemy_skill_name": self.enemy_skill_name,
            "enemy_hp_prev": self.enemy_hp_prev,
            "enemy_hp_delta": self.enemy_hp_delta,
            "enemy_eid": self.enemy_eid,
            "status": list(self.status),
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
        }


@dataclass(slots=True)
class BattleReport:
    uid: int | None
    title: str = "战斗战报"
    factor_name: str = ""
    design_id: int | None = None
    stage_index: int | None = None
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

    # 先把 S2C 帧抽出来 → 我方满血映射 + 敌方满血
    s2c = [e for e in timeline if e.get("dir") == "s2c"]
    my_max: dict[int, int] = {}
    known = set(catches)
    for e in s2c:
        if e["cmd"] == S2C_START:
            my_max = _team_max_hp_from_2504(bytes.fromhex(e["body"]), known)
            break

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

    for e in timeline:
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
                rep.turns.append(cur)
            elif cmd == C2S_SWITCH and len(body) >= 4:
                active_catch = struct.unpack_from(">I", body, 0)[0] & 0xFFFFFFFF
                if cur is not None:
                    cur.switch_to_catch = active_catch
                    cur.my_hp_max = my_max.get(active_catch)
        elif d == "s2c" and cur is not None:
            if cmd == S2C_SKILL:
                en = _enemy_head_block(body, known)
                if en is None:
                    for r in _settle_records(body, my_catches=known):
                        if r["role"] == "enemy":
                            en = r
                            break
                if en is not None:
                    if enemy_max_hp is None or en["max_hp"] != enemy_max_hp:
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
                if cur.active_catch is not None:
                    for r in _settle_records(body, my_catches=known):
                        if r["role"] == "my" and r["id"] == cur.active_catch:
                            cur.my_hp = r["hp"]
                            if r["max_hp"]:
                                cur.my_hp_max = r["max_hp"]
                            break
            elif cmd == S2C_OVER:
                rep.result.over = True
                if not rep.result.winner:
                    rep.result.winner = "战斗结束(未判胜负)"
            elif cmd == S2C_WIN:
                rep.result.passed = True
                rep.result.winner = "胜利"
            elif cmd == S2C_PROGRESS:
                rep.result.passed = True
                rep.result.winner = "胜利"

    # 第二部分：结果汇总
    rep.result.turns = len(rep.turns)
    if rep.turns:
        last = rep.turns[-1]
        rep.result.enemy_hp = last.enemy_hp
        rep.result.enemy_hp_max = last.enemy_hp_max or enemy_max_hp
        rep.result.my_hp = last.my_hp
        rep.result.my_hp_max = last.my_hp_max
    if not rep.result.winner:
        rep.result.winner = "未结束"

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
        sw = f" → 换宠 0x{t.switch_to_catch:08x}" if t.switch_to_catch else ""
        esk = t.enemy_skill_name or (f"技能id={t.enemy_skill_id}" if t.enemy_skill_id is not None else "")
        enemy = f"敌血 {t.enemy_hp}/{t.enemy_hp_max}" if t.enemy_hp is not None else ""
        my = f"我血 {t.my_hp}/{t.my_hp_max}" if t.my_hp is not None else ""
        dmg = f" 伤害~{t.damage}" if t.damage is not None else ""
        edelta = f" 敌血变化{t.enemy_hp_delta:+d}" if t.enemy_hp_delta is not None else ""
        eact = f" 敌用:{esk}" if esk else ""
        status = f" 状态[{','.join(t.status)}]" if t.status else ""
        L.append(f"  第{t.turn}回合 [{who}] {sk}{sw}{eact}  {enemy}{edelta}  {my}{dmg}{status}")
    L.append("")
    L.append("【结果】")
    r = rep.result
    L.append(f"  胜败：{r.winner or '未结束'}   结束(2506)={'是' if r.over else '否'}   过关(45827)={'是' if r.passed else '否'}")
    L.append(f"  总回合：{r.turns}")
    if r.enemy_hp is not None:
        L.append(f"  结束时敌血 {r.enemy_hp}/{r.enemy_hp_max or '?'}")
    if r.my_hp is not None:
        L.append(f"  结束时我血 {r.my_hp}/{r.my_hp_max or '?'}")
    if rep.notes:
        L.append("")
        L.append("【说明】")
        for n in rep.notes:
            L.append(f"  - {n}")
    return "\n".join(L)