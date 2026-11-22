# -*- coding: utf-8 -*-
"""机制标签提取（trait 文本 → pve:Mechanic 标签集合）。
这是『派生层』：只用于相似召回 / 占比统计 / 打标签；原始 traits 仍是权威，
抽取不到就留空，不虚构。标签集与 ontology/seer-pve.ttl 的 pve:Mechanic 一一对应。

用法：
    from mechanisms import extract, TAGS
    extract("必先；封属；300固伤；免疫物攻；减伤16.7%")  -> ["firstStrike", "sealAttr", "fixedDamage", "immunePhysical", "damageReduction"]
"""
import re

# (slug, 中文名, 匹配正则)。顺序=优先级（长/具体在前）。
TAGS = [
    ("singlePet",       "单精灵",       r"单精灵|只能(?:携带|出)|只可(?:携带|出)|仅.{0,2}只"),
    ("onlyFirstStrike", "只吃先制",     r"只吃先制|免疫非先制|先制.{0,6}(?:才|能).{0,4}(?:伤|有效)"),
    ("immunePower",     "免疫威力",     r"免疫威力|威力\s*[≤≥<>]|只吃威力|威力(?:大于|小于|以上|以下)"),
    ("rawCap",          "裸伤上限",     r"裸伤|面板.{0,8}(?:免疫|超过|低于)|免疫(?:低于|超过|高于)\s*\d|免疫面板.{0,6}"),
    ("panelImmune",     "面板免疫",     r"面板免疫|免疫面板"),
    ("immunePhysical",  "免疫物攻",     r"免疫(?:物理|物攻)"),
    ("immuneSpecial",   "免疫特攻",     r"免疫(?:特殊|特攻)"),
    ("onlyCrit",        "只吃暴击",     r"只吃暴击|非暴击|暴击(?:才能|才可|才有)"),
    ("hitDebuff",       "命中弱化",     r"命中弱化|降(?:低)?命中|命中下|命中.{0,2}弱化"),
    ("dodge",           "高闪避",       r"闪避|非必中必miss|必miss"),
    ("reflection",      "反伤",         r"反伤|反弹|反震"),
    ("shield",          "护盾",         r"护盾|盾罩"),
    ("clearPP",         "清PP",         r"清\s*PP|技能PP|PP被清|清.{0,2}个技能PP"),
    ("twoLife",         "两命",         r"两命|多命|复活"),
    ("undying",         "免死",         r"免死|不死|留\s?1血|残留1血"),
    ("heal",            "回血",         r"回满|回血|月亮|吸血|回复.*体力|恢复.*体力"),
    ("selfBuff",        "Boss强化",     r"全属性\s*\+|自身.{0,3}强化|越打越强"),
    ("debuff",          "随机弱化",     r"随机弱化|弱化|全属性\s*-"),
    ("clearBuff",       "消强",         r"消强|驱散|消除(?:我方)?能力提升|清除(?:我方)?强化"),
    ("stealBuff",       "吸强",         r"吸强|偷强|偷取强化|吸取(?:对手)?能力"),
    ("breakTurn",       "断回合",       r"断回合|清回合"),
    ("control",         "控场",         r"害怕|麻痹|石化|冰封|睡眠|焚烬|感染|控场"),
    ("bossCrit",        "Boss必暴",     r"必暴|必定暴击|概率暴击|暴击回满"),
    ("firstStrike",     "必先",         r"必先|必定先手|先制\s*\+"),
    ("sealAttr",        "封属",         r"封属|属性技能.{0,6}(?:失效|无效|封|禁止)"),
    ("fixedDamage",     "固伤",         r"固伤|固定伤害|真伤吸血"),
    ("damageReduction", "减伤",         r"减伤"),
]

SLUG2CI = {slug: cn for slug, cn, _ in TAGS}
CI2SLUG = {cn: slug for slug, cn, _ in TAGS}
SLUG2RE = {slug: re.compile(pat) for slug, _, pat in TAGS}


def extract(trait_text):
    """返回按 TAGS 顺序命中的 slug 列表（去重、保序）。"""
    if not trait_text:
        return []
    out = []
    for slug, _, _ in TAGS:
        if SLUG2RE[slug].search(trait_text) and slug not in out:
            out.append(slug)
    return out


if __name__ == "__main__":
    demo = [
        "必先；封属；300固伤；免疫物攻；消强(驱散)；减伤16.7%",
        "单精灵；必先；封属；500固伤；月亮(回血)；50%害怕控；减伤33.3%",
        "必先；封属；只吃先制伤害；真伤吸血300；消强",
        "必先；封属；反弹50%红伤；免疫威力>100；两命",
    ]
    for t in demo:
        print(t)
        print("  ->", extract(t))