"""用 seerapi（公开数据，无需账号授权）初始化领域知识库的精灵/技能数据文件。

产物（写到 seer_rebuild/domain_knowledge/）：
  - pets.json   : species_id -> {name, type, boss, soulmark_tags[], skills[]}
  - skills.json : skill_id -> {name, power, cat, type, priority, desc, tags[]}

技能与魂印效果会按关键词自动归类到受控标签（tags.json 里的词表）。

用法：
    python scripts/init_domain_knowledge.py
"""
from __future__ import annotations

import json
from pathlib import Path

from seer_rebuild.provider import SeerApiProvider

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "seer_rebuild" / "domain_knowledge"

# 因子相关精灵 + 已识别的 BOSS（species_id, 外号, 是否boss）
PET_LIST: list[tuple[int, list[str], bool]] = [
    # 出战精灵 / 常见打因子宠物
    (3512, ["表姐"], False),          # 帝皇之御
    (3045, ["六界神王", "六界"], False),
    (3463, ["时空界皇", "时空"], False),
    (3192, ["天香小乔", "小乔"], False),
    (2654, ["喵奇"], False),
    (3473, ["尖啸风怪"], False),
    (5000, ["圣灵谱尼", "圣谱"], False),
    (3022, ["王之哈莫", "王哈"], False),
    (4649, ["星光·魔焰猩猩"], False),
    (4606, ["加尔鲁特"], False),
    # 戟决先锋(design 228) 5 关 BOSS
    (3618, [], True), (3595, [], True), (3599, ["卡杉德拉"], True), (3978, [], True), (4857, ["戟决先锋"], True),
    # 谜之英雄(design 225) BOSS
    (4539, ["文森特"], True), (4330, [], True), (4137, [], True), (4845, [], True), (4848, ["谜之英雄"], True),
    # 灵巢之主(design 141) BOSS
    (4569, [], True), (4568, [], True), (4594, [], True), (4597, [], True), (4599, ["索杰德尔"], True),
    # 沙罗摩奥(design 267) BOSS
    (3296, [], True), (4531, [], True), (4938, ["塞壬斯"], True), (4625, [], True), (4965, ["沙罗摩奥"], True),
]

# 受控标签的命中关键词（按顺序，先命中谁就带谁）
TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("自爆", ("消耗自身全部体力", "消耗自身所有体力", "消耗自身体力")),
    ("弹伤", ("反馈", "反弹", "反伤")),
    ("保命", ("保留1点体力", "残留1点体力", "保留1点", "致死伤害")),
    ("免疫致命", ("免疫致命", "免暴击")),
    ("免疫攻击", ("免疫下", "免疫对手的攻击", "免疫受到的攻击", "免疫当回合伤害")),
    ("免异常", ("免疫异常", "免疫所有异常", "免疫并反弹")),
    ("免下降", ("免疫能力下降",)),
    ("必先必暴", ("必定先手必定暴击", "必先必暴")),
    ("先制", ("先制", "必定先手", "先手")),
    ("减伤", ("伤害减少", "伤害-", "减50%")),
    ("吸血", ("恢复自己", "恢复自身", "吸取", "转化为自身体力", "回血", "恢复1/3", "恢复1/4", "恢复100")),
    ("百分比伤害", ("百分比伤害", "最大体力", "已损失体力")),
    ("固定伤害", ("固定伤害",)),
    ("消回合", ("消除对手回合类效果", "消除回合")),
    ("消强", ("消除对手能力提升", "消除能力提升", "能力提升效果转化")),
    ("控", ("麻痹", "疲惫", "睡眠", "瘫痪", "害怕", "石化", "混乱", "失明", "束缚")),
    ("免控", ("免疫控制",)),
    ("强化", ("改变自身", "提升", "全属性+", "等级+", "转化到自己身上")),
    ("弱化", ("改变对手", "降低",)),
]


def tag_of_text(text: str) -> list[str]:
    hits: list[str] = []
    for tag, kws in TAG_RULES:
        if any(k in text for k in kws):
            hits.append(tag)
    return hits


def build() -> None:
    p = SeerApiProvider()
    skills: dict[int, dict] = {}
    pets: dict[int, dict] = {}

    def ensure_skill(sid: int) -> None:
        if sid in skills:
            return
        d = p.get("skill", sid, fields=["id", "name", "power", "category", "type", "priority", "must_hit", "crit_rate", "skill_effect"]) or {}
        effs = [e.get("info") or "" for e in (d.get("skill_effect") or [])]
        tags = []
        for e in effs:
            tags += tag_of_text(e)
        skills[sid] = {
            "name": d.get("name") or str(sid),
            "power": d.get("power") or 0,
            "cat": (d.get("category") or {}).get("id") or 0,
            "type": (d.get("type") or {}).get("id") or 0,
            "priority": d.get("priority") or 0,
            "desc": "；".join(effs),
            "tags": sorted(set(tags)),
        }

    for sid, aliases, is_boss in PET_LIST:
        pet = p.get("pet", sid, fields=["id", "name", "type", "soulmark", "skill"]) or {}
        name = pet.get("name") or str(sid)
        stype = (pet.get("type") or {}).get("id") or 0
        # 魂印标签
        stags: list[str] = []
        for sm in pet.get("soulmark") or []:
            smd = p.get("soulmark", sm["id"]) or {}
            desc = smd.get("desc") or ""
            if isinstance(desc, dict):
                desc = desc.get("desc") or ""
            if isinstance(desc, str):
                stags += tag_of_text(desc)
        # 技能 id
        skids = [s["skill"]["id"] for s in (pet.get("skill") or [])]
        for sk in skids:
            ensure_skill(sk)
        pets[sid] = {
            "name": name,
            "type": stype,
            "boss": is_boss,
            "aliases": aliases,
            "role_tags": [],
            "soulmark_tags": sorted(set(stags)),
            "skills": skids,
        }
        print(f"[pet] {sid} {name} boss={is_boss} skills={len(skids)} tags={sorted(set(stags))}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "skills.json").write_text(json.dumps({str(k): v for k, v in sorted(skills.items())}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "pets.json").write_text(json.dumps({str(k): v for k, v in sorted(pets.items())}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：{len(pets)} 只精灵，{len(skills)} 个技能 -> {OUT}")


if __name__ == "__main__":
    build()