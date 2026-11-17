"""赛尔号领域知识库加载器（零依赖，纯标准库 JSON）。

两个实体库 + 一层标签，位于 `seer-rebuild/domain_knowledge/`：
  - tags.json   能力标签受控词汇：tag -> 含义
  - skills.json 技能库：skill_id -> {name, power, cat, type, priority, tags[]}
  - pets.json   精灵库：species_id -> {name, aliases[], type, roles[], soulmark, skills[]}

用法：
    from seer_rebuild.domain_knowledge import load
    dk = load()
    dk.pets_with_tags(["保命", "弹伤"])   # 找具备某组能力的精灵
    dk.pet_tags(3512)                     # 某精灵的全部能力标签
    dk.skill_tags(19314)
    dk.tag_meaning("弹伤")
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent / "domain_knowledge"


@dataclass(slots=True)
class Skill:
    id: int
    name: str
    power: int
    cat: int            # 1=物攻 2=特攻 3=属性
    type: int           # element_type_combination id
    priority: int
    tags: list[str] = field(default_factory=list)
    desc: str = ""


@dataclass(slots=True)
class Pet:
    id: int
    name: str
    type: int
    aliases: list[str] = field(default_factory=list)
    role_tags: list[str] = field(default_factory=list)      # 定位标签（站场/补刀/强攻/辅助/弹伤）
    soulmark_tags: list[str] = field(default_factory=list)
    skills: list[int] = field(default_factory=list)
    boss: bool = False
    mode: str = "pve"            # 核心上层标签：pve / pvp / both（按巅峰池 heuristic，待人工校准）

    def all_tags(self) -> set[str]:
        return set(self.role_tags) | set(self.soulmark_tags)


class DomainKnowledge:
    def __init__(self, tags: dict, skills: dict, pets: dict) -> None:
        self.tags: dict[str, str] = tags
        self.skills: dict[int, Skill] = {int(k): Skill(id=int(k), **v) for k, v in skills.items()}
        self.pets: dict[int, Pet] = {int(k): Pet(id=int(k), **v) for k, v in pets.items()}

    # ---- 基础查询 ----
    def pet(self, species_id: int) -> Pet | None:
        return self.pets.get(species_id)

    def skill(self, skill_id: int) -> Skill | None:
        return self.skills.get(skill_id)

    def tag_meaning(self, tag: str) -> str:
        return self.tags.get(tag, "")

    def find_pet_by_alias(self, alias: str) -> Pet | None:
        for p in self.pets.values():
            if alias in p.aliases or alias == p.name:
                return p
        return None

    # ---- 标签能力 ----
    def skill_tags(self, skill_id: int) -> set[str]:
        s = self.skill(skill_id)
        return set(s.tags) if s else set()

    def pet_tags(self, species_id: int) -> set[str]:
        """精灵的全部标签 = 定位标签 + 魂印标签 + 所有实战技能的标签。"""
        p = self.pet(species_id)
        if not p:
            return set()
        out = set(p.role_tags) | set(p.soulmark_tags)
        for sid in p.skills:
            out |= self.skill_tags(sid)
        return out

    def pets_with_tags(self, tags: list[str], *, require_all: bool = True) -> list[Pet]:
        """找具备指定能力标签的精灵（默认要求全部具备）。"""
        want = set(tags)
        out = []
        for p in self.pets.values():
            if p.boss:
                continue
            got = self.pet_tags(p.id)
            ok = want <= got if require_all else bool(want & got)
            if ok:
                out.append(p)
        return out

    def missing_tags(self, species_id: int, tags: list[str]) -> list[str]:
        """某精灵相对于目标能力还缺哪些标签（可行性缺口）。"""
        got = self.pet_tags(species_id)
        return [t for t in tags if t not in got]


def load(base: str | Path | None = None) -> DomainKnowledge:
    base = Path(base) if base else BASE
    def _read(name: str) -> dict:
        with open(base / name, encoding="utf-8") as f:
            return json.load(f)
    return DomainKnowledge(_read("tags.json"), _read("skills.json"), _read("pets.json"))