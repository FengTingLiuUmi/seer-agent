# -*- coding: utf-8 -*-
"""add_roles.py —— 给 PVE 库精灵按消歧表文字自动标注 pve:hasRole（启发式，供后续人工校正）。
输出：seer-pve-roles.ttl
"""
import os, sys, re
from rdflib import Graph, Namespace, RDF, RDFS

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ingest import PVE_IDS  # noqa: E402

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")

# 关键词 → 角色（顺序有优先级：先命中多的）
RULES = [
    ("reflect", ["弹伤", "反弹", "反伤"]),
    ("firstStrike", ["必先", "先制", "先手"]),
    ("attacker", ["强攻", "爆攻", "秒杀", "补刀", "打手", "清场", "爆发"]),
    ("tank", ["站场", "坦克", "特防体", "防体", "攻体", "磨血", "续航", "血厚"]),
    ("support", ["辅助", "送头", "后台", "铺盾", "套盾", "减伤", "场地", "消强", "判弱", "易伤", "封印", "叠毒", "保命", "护盾"]),
]


def classify(text):
    roles = []
    for role, kws in RULES:
        if any(k in text for k in kws):
            roles.append(PVE[role])
    return roles


def main():
    g = Graph()
    g.parse(os.path.join(HERE, "seer-pve-alias.ttl"), format="turtle")

    out = Graph()
    out.bind("seer", SEER)
    out.bind("pve", PVE)

    n = 0
    for pid in PVE_IDS:
        s = SEER[f"pet_{pid}"]
        label = str(g.value(s, RDFS.label) or "")
        comment = str(g.value(s, RDFS.comment) or "")
        text = label + " " + comment
        roles = classify(text)
        for r in roles:
            out.add((s, PVE.hasRole, r))
        if roles:
            n += 1

    outp = os.path.join(HERE, "seer-pve-roles.ttl")
    out.serialize(outp, format="turtle")
    print("已标注", n, "只（共", len(PVE_IDS), "只）")
    print("输出", outp, "三元组", len(out))


if __name__ == "__main__":
    main()