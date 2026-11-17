"""第 2 轮：优化标签覆盖 + 精修 mode + 生成 role 建议（不覆盖已策展 role_tags）。

1) 追加 TAG_RULES 关键词；重抓魂印原文存 soulmark_desc；重打魂印+技能标签。
2) mode 精修：seerapi peak_pool/peak_expert_pool 或 本地 PvpBan.ini/pvp_ban_expert.ini => pvp。
3) role 建议（机制->定位，仅打印建议，不写 role_tags，避免覆盖人工策展）。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from seer_rebuild.provider import SeerApiProvider

BASE = Path(__file__).resolve().parent.parent / "seer_rebuild" / "domain_knowledge"

TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("自爆", ("消耗自身全部体力", "消耗自身所有体力", "消耗自身体力", "牺牲")),
    ("弹伤", ("反馈", "反弹", "反伤", "弹伤")),
    ("保命", ("保留1点体力", "残留1点体力", "残留1点血", "保留1点", "复活", "重生", "涅槃")),
    ("免疫致命", ("免疫致命", "免暴击", "免疫暴击")),
    ("免疫攻击", ("免疫下", "免疫对手的攻击", "免疫受到的攻击", "免疫当回合伤害", "抵挡", "免疫攻击", "免疫伤害", "锁伤")),
    ("免异常", ("免疫异常", "免疫所有异常", "免疫并反弹", "免疫控制")),
    ("免下降", ("免疫能力下降",)),
    ("必先必暴", ("必定先手必定暴击", "必先", "必定暴击")),
    ("先制", ("先制", "必定先手", "先手", "必先")),
    ("减伤", ("伤害减少", "伤害-", "减50%", "减伤", "伤害减免")),
    ("吸血", ("恢复自己", "恢复自身", "吸取", "转化为自身体力", "回血", "恢复1/3", "恢复1/4", "恢复100", "恢复全部", "回复体力")),
    ("百分比伤害", ("百分比伤害", "最大体力", "已损失", "生命值", "当前体力")),
    ("固定伤害", ("固定伤害",)),
    ("消回合", ("消除对手回合类效果", "消除回合")),
    ("消强", ("消除对手能力提升", "消除能力提升", "能力提升效果转化", "反转对手能力提升")),
    ("控", ("麻痹", "疲惫", "睡眠", "瘫痪", "害怕", "石化", "混乱", "失明", "束缚", "定身", "冰封", "恐惧")),
    ("免控", ("免疫控制",)),
    ("强化", ("改变自身", "提升", "全属性+", "等级+", "转化到自己身上", "强化")),
    ("弱化", ("改变对手", "降低")),
    ("增伤", ("伤害提高", "伤害翻倍", "威力翻倍", "伤害提升", "威力提高", "伤害加倍")),
]


def tag_of(text: str) -> list[str]:
    out = []
    for t, kws in TAG_RULES:
        if any(k in text for k in kws):
            out.append(t)
    return out


# 本地 PVP 名单（GBK）
def local_pvp_set() -> set[int]:
    out: set[int] = set()
    for f in ("PvpBan.ini", "pvp_ban_expert.ini"):
        p = Path(r"F:\seer\seer_cfg\json") / f
        if not p.exists():
            continue
        txt = p.read_bytes().decode("gbk", "replace")
        for tok in ("Name=", "ban="):
            if tok in txt:
                for part in txt.split(tok)[1:]:
                    head = part.split("\n")[0]
                    for x in head.replace(";", ",").split(","):
                        x = x.strip()
                        if x.isdigit():
                            out.add(int(x))
    return out


# ---- role 建议（保守）----
def suggest_role(soulmark_tags: list[str], skill_tags_map: dict, skills: list[int]) -> list[str]:
    st = set(soulmark_tags)
    allt = set(soulmark_tags)
    max_power = 0
    for sid in skills:
        t = set(skill_tags_map.get(sid, []))
        allt |= t
    roles: list[str] = []
    if "弹伤" in allt:
        roles.append("弹伤")
    if {"保命", "减伤"} <= allt or {"保命", "免异常", "减伤"} <= allt:
        roles.append("站场")
    if {"固定伤害", "百分比伤害"} & allt and "先制" in allt:
        roles.append("补刀")
    if "自爆" in allt or "必先必暴" in allt:
        roles.append("辅助")
    # 高威力 -> 强攻（保守：再看领队角色是否已判定）
    return roles or []


def main() -> None:
    p = SeerApiProvider()
    pvp = local_pvp_set()
    pets = json.load(open(BASE / "pets.json", encoding="utf-8"))
    skills = json.load(open(BASE / "skills.json", encoding="utf-8"))

    # 1) 技能 desc 重打标签（本地，快）
    for sid, s in skills.items():
        s["tags"] = sorted(set(tag_of(s.get("desc", ""))))

    # 2) 魂印原文重抓 + 重打标签
    suggestions: dict[int, list[str]] = {}
    for sid, pt in pets.items():
        try:
            d = p.get("pet", int(sid), fields=["id", "peak_pool", "peak_expert_pool", "soulmark"]) or {}
        except Exception:
            d = {}
        if pt.get("boss"):
            continue
        # mode 精修
        is_pvp = bool(d.get("peak_pool") or d.get("peak_expert_pool")) or (int(sid) in pvp)
        pt["mode"] = "pvp" if is_pvp else "pve"
        # 魂印原文
        descs = []
        for sm in (d.get("soulmark") or []):
            try:
                smd = p.get("soulmark", sm["id"]) or {}
            except Exception:
                smd = {}
            desc = smd.get("desc") or ""
            if isinstance(desc, dict):
                desc = desc.get("desc") or ""
            if isinstance(desc, str):
                descs.append(desc)
        if descs:
            pt["soulmark_desc"] = "|".join(descs)
            pt["soulmark_tags"] = sorted(set(t for desc in descs for t in tag_of(desc)))
        # role 建议（只建议，不覆盖人工 role_tags）
        st = set(pt.get("soulmark_tags") or [])
        sk_map = {int(k): set(v["tags"]) for k, v in skills.items()}
        skids = [int(x) for x in pt.get("skills") or []]
        if not pt.get("role_tags"):
            suggestions[int(sid)] = suggest_role(list(st), sk_map, skids)

    (BASE / "skills.json").write_text(json.dumps(skills, ensure_ascii=False, indent=2), encoding="utf-8")
    (BASE / "pets.json").write_text(json.dumps(pets, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    mc = Counter(v.get("mode") for v in pets.values())
    print("mode 精修后:", dict(mc))
    print("\n===== role 建议（待你确认，未写入）=====")
    for sid, roles in suggestions.items():
        nm = pets[str(sid)].get("name")
        print(f"{sid} {nm}: 建议 role={roles}  魂印tags={pets[str(sid)].get('soulmark_tags')}")
    print(f"\n完成：pets={len(pets)} skills={len(skills)}")


if __name__ == "__main__":
    main()