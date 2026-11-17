"""初始化大号精英收藏(2361)的精灵/魂印/技能，打上 PV(E/P) 核心上层标签 + 机制标签。

只读 seerapi（无账号授权）；技能/魂印效果自动归类到受控标签。
PVP 判断：seerapi `peak_pool`/`peak_expert_pool` 非空 => pvp，否则 pve。
（人工校准：双修宠如圣灵谱尼其实 both，后续在 pets.json 改 mode 即可。）

产物：seer_rebuild/domain_knowledge/pets.json + skills.json
保留已人工策展的 role_tags / aliases。
"""
from __future__ import annotations

import json
from pathlib import Path

from seer_rebuild.provider import SeerApiProvider

BASE = Path(__file__).resolve().parent.parent / "seer_rebuild" / "domain_knowledge"

# 大号精英收藏(2361) 去重后的 species（131 条 → 125 只去重物种）
SPECIES = [
    2987,3221,3022,5000,3218,3239,3194,4169,3437,3118,3644,3463,3623,3409,2727,
    3456,3056,3894,4093,3711,3637,3577,3673,3291,3512,3697,3976,4068,3561,4184,
    3329,3866,3568,3414,3465,3668,3328,4007,3916,3679,3425,3670,3994,3467,4001,
    3741,3788,3033,3986,4002,4321,4355,4004,4208,3516,4354,4347,4275,4353,4373,
    3667,3631,4377,4386,4126,4279,4391,4398,4397,4345,3045,4338,4387,4450,4462,
    4463,4468,3388,3567,4498,3507,4496,4422,4510,4500,4515,4288,4344,3684,4541,
    4554,3705,4586,4636,4606,4622,4643,4649,4648,4647,4644,4329,3491,4677,4487,
    4853,4223,2933,4000,4454,4163,4732,4903,4911,4872,4511,4766,4800,4912,4553,
    4797,4875,4808,3141,2977,
]

TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("自爆", ("消耗自身全部体力", "消耗自身所有体力", "消耗自身体力")),
    ("弹伤", ("反馈", "反弹", "反伤")),
    ("保命", ("保留1点体力", "残留1点体力", "残留1点血", "保留1点")),
    ("免疫致命", ("免疫致命", "免暴击")),
    ("免疫攻击", ("免疫下", "免疫对手的攻击", "免疫受到的攻击", "免疫当回合伤害")),
    ("免异常", ("免疫异常", "免疫所有异常", "免疫并反弹")),
    ("免下降", ("免疫能力下降",)),
    ("必先必暴", ("必定先手必定暴击",)),
    ("先制", ("先制", "必定先手", "先手", "必先")),
    ("减伤", ("伤害减少", "伤害-", "减50%")),
    ("吸血", ("恢复自己", "恢复自身", "吸取", "转化为自身体力", "回血", "恢复1/3", "恢复1/4", "恢复100")),
    ("百分比伤害", ("百分比伤害", "最大体力", "已损失", "生命值")),
    ("固定伤害", ("固定伤害",)),
    ("消回合", ("消除对手回合类效果", "消除回合")),
    ("消强", ("消除对手能力提升", "消除能力提升", "能力提升效果转化", "反转对手能力提升")),
    ("控", ("麻痹", "疲惫", "睡眠", "瘫痪", "害怕", "石化", "混乱", "失明", "束缚")),
    ("免控", ("免疫控制",)),
    ("强化", ("改变自身", "提升", "全属性+", "等级+", "转化到自己身上")),
    ("弱化", ("改变对手", "降低")),
]


def tag_of(text: str) -> list[str]:
    out = []
    for t, kws in TAG_RULES:
        if any(k in text for k in kws):
            out.append(t)
    return out


def main() -> None:
    p = SeerApiProvider()
    old_pets = json.load(open(BASE / "pets.json", encoding="utf-8"))
    skills: dict[int, dict] = json.load(open(BASE / "skills.json", encoding="utf-8"))
    pets: dict[int, dict] = dict(old_pets)

    def ensure_skill(sid: int) -> None:
        if str(sid) in skills:
            return
        d = p.get("skill", sid, fields=["id", "name", "power", "category", "type", "priority", "must_hit", "crit_rate", "skill_effect"]) or {}
        effs = [e.get("info") or "" for e in (d.get("skill_effect") or [])]
        tags = []
        for e in effs:
            tags += tag_of(e)
        skills[str(sid)] = {
            "name": d.get("name") or str(sid), "power": d.get("power") or 0,
            "cat": (d.get("category") or {}).get("id") or 0, "type": (d.get("type") or {}).get("id") or 0,
            "priority": d.get("priority") or 0, "desc": "；".join(effs), "tags": sorted(set(tags)),
        }

    for i, sid in enumerate(SPECIES, 1):
        d = p.get("pet", sid, fields=["id", "name", "type", "peak_pool", "peak_expert_pool", "soulmark", "skill"]) or {}
        name = d.get("name") or str(sid)
        mode = "pvp" if (d.get("peak_pool") or d.get("peak_expert_pool")) else "pve"
        old = pets.get(str(sid)) or {}
        if str(sid) in pets:
            # 已有人工策展的 role_tags/aliases 保留，只补 mode
            pets[str(sid)]["mode"] = mode
            print(f"[skip] {i:3d} {sid} {name} mode={mode} (已有策展)")
            continue
        stags = []
        for sm in d.get("soulmark") or []:
            smd = p.get("soulmark", sm["id"]) or {}
            desc = smd.get("desc") or ""
            if isinstance(desc, dict):
                desc = desc.get("desc") or ""
            if isinstance(desc, str):
                stags += tag_of(desc)
        skids = [s["skill"]["id"] for s in (d.get("skill") or [])]
        for sk in skids:
            ensure_skill(sk)
        pets[str(sid)] = {
            "name": name, "type": (d.get("type") or {}).get("id") or 0, "boss": False,
            "aliases": old.get("aliases") or [], "role_tags": old.get("role_tags") or [],
            "soulmark_tags": sorted(set(stags)), "skills": skids, "mode": mode,
        }
        print(f"[add] {i:3d} {sid} {name} mode={mode} soulmark_tags={sorted(set(stags))}")

    (BASE / "skills.json").write_text(json.dumps({str(k): v for k, v in sorted(skills.items(), key=lambda x: int(x[0]))}, ensure_ascii=False, indent=2), encoding="utf-8")
    (BASE / "pets.json").write_text(json.dumps({str(k): pets[k] for k in sorted(pets, key=int)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：pets={len(pets)} skills={len(skills)}")


if __name__ == "__main__":
    main()