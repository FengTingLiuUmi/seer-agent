"""本地战斗数据：monsters_pro / moves / skill_effect / BossEffect / 属性克制。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .ini_util import IniDoc, as_float, as_ids, as_int, load_ini


@dataclass(slots=True)
class Move:
    id: int
    name: str
    power: int
    category: int  # 1=物攻 2=特攻 3=属性
    type: int
    priority: int
    accuracy: float
    must_hit: bool
    crit_rate: float
    side_effects: list[int] = field(default_factory=list)
    side_args: list[int] = field(default_factory=list)


@dataclass(slots=True)
class Species:
    id: int
    name: str
    type: int
    skills: list[int]
    base: dict[str, int]
    gender: int = 0
    real_id: int = 0


@dataclass(slots=True)
class Pet:
    species: Species
    level: int = 100
    name: str = ""
    hp: int = 0
    max_hp: int = 0
    stats: dict[str, int] = field(default_factory=dict)
    skills: list[int] = field(default_factory=list)
    boosts: dict[str, int] = field(default_factory=dict)
    status: set[str] = field(default_factory=set)
    effects: dict[str, int] = field(default_factory=dict)
    fainted: bool = False
    side: str = "player"

    @property
    def alive(self) -> bool:
        return not self.fainted and self.hp > 0


@dataclass(slots=True)
class BossTrait:
    id: int
    args: list[int]
    text: str


# monsters_pro.ini / moves.ini 的 Type 数值；与 typesRelation.ini 的中文键对应。
TYPE_NAMES: dict[int, str] = {
    1: "草", 2: "水", 3: "火", 4: "飞行", 5: "电", 6: "机械", 7: "地面", 8: "普通",
    9: "冰", 10: "超能", 11: "战斗", 12: "光", 13: "暗影", 14: "神秘", 15: "龙",
    16: "圣灵", 17: "次元", 18: "远古", 19: "邪灵", 20: "自然", 21: "虫", 22: "王",
    23: "混沌", 24: "神灵", 25: "轮回", 26: "虚空",
}


class BattleData:
    def __init__(self, root: str | Path, provider: Any | None = None):
        root = Path(root)
        self.root = root
        self.provider = provider
        self.species: dict[int, Species] = {}
        self.moves: dict[int, Move] = {}
        self.effects: dict[int, dict[str, str]] = {}
        self.types: dict[str, dict[str, float]] = {}
        self.boss_effects: dict[int, list[BossTrait]] = {}
        self._load()

    def _load(self) -> None:
        if (self.root / "monsters_pro.ini").exists():
            doc = load_ini(self.root / "monsters_pro.ini")
            for sec, kv in doc.sections:
                try:
                    sid = int(sec)
                except ValueError:
                    continue
                base = {
                    "hp": as_int(kv.get("体力")),
                    "atk": as_int(kv.get("物攻")),
                    "def": as_int(kv.get("物防")),
                    "sp_atk": as_int(kv.get("特攻")),
                    "sp_def": as_int(kv.get("特防")),
                    "spd": as_int(kv.get("速度")),
                }
                self.species[sid] = Species(
                    id=sid,
                    name=kv.get("Name", str(sid)),
                    type=as_int(kv.get("Type")),
                    skills=as_ids(kv.get("Skills")),
                    base=base,
                    gender=as_int(kv.get("Gender")),
                    real_id=as_int(kv.get("RealId")),
                )
        if (self.root / "moves.ini").exists():
            doc = load_ini(self.root / "moves.ini")
            for sec, kv in doc.sections:
                try:
                    mid = int(sec)
                except ValueError:
                    continue
                self.moves[mid] = Move(
                    id=mid,
                    name=kv.get("name", str(mid)),
                    power=as_int(kv.get("power")),
                    category=as_int(kv.get("Category")),
                    type=as_int(kv.get("Type")),
                    priority=as_int(kv.get("Priority")),
                    accuracy=as_float(kv.get("Accuracy"), 100.0),
                    must_hit=as_int(kv.get("MustHit")) == 1,
                    crit_rate=as_float(kv.get("CritRate"), 6.25),
                    side_effects=as_ids(kv.get("SideEffect")),
                    side_args=as_ids(kv.get("SideEffectArg")),
                )
        if (self.root / "skill_effect.ini").exists():
            doc = load_ini(self.root / "skill_effect.ini")
            for sec, kv in doc.sections:
                try:
                    eid = int(sec)
                except ValueError:
                    continue
                self.effects[eid] = kv
        if (self.root / "typesRelation.ini").exists():
            doc = load_ini(self.root / "typesRelation.ini")
            for sec, kv in doc.sections:
                self.types[sec] = {k: as_float(v, 1.0) for k, v in kv.items()}
        if (self.root / "BossEffect.ini").exists():
            doc = load_ini(self.root / "BossEffect.ini")
            for sec, kv in doc.sections:
                try:
                    bid = int(sec)
                except ValueError:
                    continue
                traits: list[BossTrait] = []
                for k, v in kv.items():
                    if k in ("iconId", "sort"):
                        continue
                    args = as_ids(k)
                    traits.append(BossTrait(bid, args, v))
                self.boss_effects[bid] = traits

    # ------------------------------------------------------------------
    def make_pet(self, species_id: int, *, level: int = 100, name: str | None = None, side: str = "player",
                 stat_overrides: dict[str, int] | None = None, skills: Iterable[int] | None = None) -> Pet:
        sp = self.species.get(species_id)
        if sp is None:
            raise KeyError(f"unknown species {species_id}")
        stats = self.compute_stats(sp, level)
        if stat_overrides:
            stats.update(stat_overrides)
        p = Pet(
            species=sp,
            level=level,
            name=name or sp.name,
            hp=stats["hp"],
            max_hp=stats["hp"],
            stats=stats,
            skills=list(skills if skills is not None else sp.skills[:4]),
            boosts={"atk": 0, "def": 0, "sp_atk": 0, "sp_def": 0, "spd": 0},
            side=side,
        )
        return p

    @staticmethod
    def compute_stats(sp: Species, level: int = 100, iv: int = 31) -> dict[str, int]:
        b = sp.base
        return {
            "hp": (b["hp"] * 2 + iv) * level // 100 + level + 10,
            "atk": (b["atk"] * 2 + iv) * level // 100 + 5,
            "def": (b["def"] * 2 + iv) * level // 100 + 5,
            "sp_atk": (b["sp_atk"] * 2 + iv) * level // 100 + 5,
            "sp_def": (b["sp_def"] * 2 + iv) * level // 100 + 5,
            "spd": (b["spd"] * 2 + iv) * level // 100 + 5,
        }

    def type_multiplier(self, attack_type: int, defender_type: int | None) -> float:
        if defender_type is None:
            return 1.0
        return self.type_multiplier_name(TYPE_NAMES.get(attack_type, ""), TYPE_NAMES.get(defender_type, ""))

    def type_multiplier_name(self, attack_name: str, defender_name: str) -> float:
        row = self.types.get(attack_name, {})
        return row.get(defender_name, 1.0)

    def effect_tag(self, effect_id: int) -> str:
        kv = self.effects.get(effect_id, {})
        return kv.get("tagA", "") or kv.get("info", "")

    def traits_for(self, boss_id: int) -> list[BossTrait]:
        return self.boss_effects.get(boss_id, [])

    # ------------------------------------------------------------------
    # 可选 SeerAPI 反查：优先在线，失败返回本地
    def pet_name(self, species_id: int) -> str:
        if self.provider is not None:
            name = self.provider.resolve("pet", species_id)
            if name:
                return name
        return self.species.get(species_id, Species(species_id, str(species_id), 0, [], {})).name if hasattr(self.species.get(species_id), "name") else str(species_id)

    def skill_name(self, move_id: int) -> str:
        if self.provider is not None:
            name = self.provider.resolve("skill", move_id)
            if name:
                return name
        m = self.moves.get(move_id)
        return m.name if m else str(move_id)

    def item_name(self, item_id: int) -> str:
        if self.provider is not None:
            return self.provider.resolve("item", item_id) or str(item_id)
        return str(item_id)