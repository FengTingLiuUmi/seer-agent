# -*- coding: utf-8 -*-
"""
owlready2 本体检查脚本 —— 检查赛尔号（游戏本体 + PVE 打法层）的定义是否自洽。
加载 seer-game.owl + seer-pve.owl，列出类/属性/个体，并跑 HermiT 推理查一致性。
用法（需 owlready2，推理需 java 在 PATH）：
    python check_onto.py
"""
import os
from owlready2 import *

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "seer-game.owl").replace("\\", "/")
PVE = os.path.join(HERE, "seer-pve.owl").replace("\\", "/")

print("加载游戏本体:", GAME)
game = get_ontology(GAME).load()
print("加载 PVE 打法层:", PVE)
pve = get_ontology(PVE).load()

for name, onto in [("seer-game", game), ("seer-pve", pve)]:
    print("\n=== [%s] 类 (%d) ===" % (name, len(list(onto.classes()))))
    for c in onto.classes():
        lab = c.label.first() if c.label else ""
        print("  o %s | %s" % (c.name, lab))
    print("=== [%s] 对象属性 (%d) ===" % (name, len(list(onto.object_properties()))))
    for p in onto.object_properties():
        print("  -", p.name)
    print("=== [%s] 数据属性 (%d) ===" % (name, len(list(onto.data_properties()))))
    for p in onto.data_properties():
        print("  -", p.name)
    print("=== [%s] 个体 (%d) ===" % (name, len(list(onto.individuals()))))
    for i in onto.individuals():
        lab = i.label.first() if i.label else ""
        print("  o %s | %s" % (i.name, lab))

print("\n=== 一致性推理（HermiT，需要 java）===")
try:
    with pve:  # pve imports game，推理 pve 即覆盖两层
        sync_reasoner_hermit()
    inc = list(default_world.inconsistent_classes())
    print("  HermiT 完成；不一致类:", [c.name for c in inc] or "无（本体一致）")
except Exception as e:
    print("  推理跳过:", str(e)[:200])