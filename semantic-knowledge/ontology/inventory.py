# -*- coding: utf-8 -*-
"""输出当前本体的完整知识盘点（类→实例数 + 关键统计）。"""
import os
from collections import Counter
from rdflib import Graph, RDF, OWL, RDFS, Namespace, SKOS

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

g = Graph()
g.parse(f"{HERE}/seer-all.owl", format="xml")

print("总三元组 =", len(g))

def ln(u):
    return str(u).split("#")[-1]

classes = set(g.subjects(RDF.type, OWL.Class))
print("\n== 类 → 个体数 ==")
byclass = Counter(o for o in g.objects(None, RDF.type) if o in classes)
for c in sorted(classes, key=ln):
    print(f"  {ln(c):28s} {byclass.get(c, 0)}")

objprops = set(g.subjects(RDF.type, OWL.ObjectProperty))
dtprops = set(g.subjects(RDF.type, OWL.DatatypeProperty))
print(f"\nObjectProperty={len(objprops)}  DatatypeProperty={len(dtprops)}")

# 别名
aliases = list(g.objects(None, SKOS.altLabel))
print(f"\n昵称别名(skos:altLabel) = {len(aliases)}")

# 角色
roles = set(o for o in g.objects(None, PVE.hasRole))
print(f"hasRole 三元组 = {len(list(g.objects(None, PVE.hasRole)))}, 角色取值 = {sorted(ln(r) for r in roles)}")

# 技能相关
skills = set(g.subjects(RDF.type, SEER.Skill))
print(f"\nSkill 个体 = {len(skills)}")
for pred, name in [(SEER.skillType, "skillType"), (SEER.hasSkillEffect, "hasSkillEffect")]:
    print(f"  有{name} = {len(set(g.subjects(pred, None)))}")
fx = set(g.subjects(RDF.type, PVE.SkillEffect))
print(f"  SkillEffect 个体 = {len(fx)}, bossEffective=true 的 = {len(set(s for s in g.subjects(PVE.bossEffective, None)))}")
sm = set(g.subjects(RDF.type, SEER.Soulmark))
print(f"Soulmark 个体 = {len(sm)}, pveEffective = {len(set(g.subjects(PVE.pveEffective, None)))}")

# 属性表
ET = set(g.subjects(RDF.type, SEER.ElementType))
TC = set(g.subjects(RDF.type, SEER.TypeCombination))
TR = set(g.subjects(RDF.type, SEER.TypeRelation))
print(f"\nElementType = {len(ET)}  TypeCombination = {len(TC)}  TypeRelation(克矩阵) = {len(TR)}")
for pred in [SEER.counters, SEER.resisted, SEER.immune]:
    print(f"  {ln(pred)} = {len(set(g.subjects(pred, None)))}")

# 装备
for cls, name in [(SEER.Suit, "Suit套装"), (SEER.Title, "Title称号"), (SEER.Nature, "Nature性格"), (SEER.Fire, "Fire火焰")]:
    print(f"{name} = {len(set(g.subjects(RDF.type, cls)))}")

# Boss/因子
fac = set(g.subjects(RDF.type, SEER.Factor))
st = set(g.subjects(RDF.type, SEER.FactorStage))
en = set(g.subjects(RDF.type, PVE.Enemy))
fd = set(g.subjects(RDF.type, PVE.FactorDifficulty))
print(f"\nFactor = {len(fac)}  FactorStage = {len(st)}  Enemy = {len(en)}  FactorDifficulty = {len(fd)}")
dc = Counter(ln(o) for o in g.objects(None, PVE.difficulty))
print("  难度分布 =", dict(dc))
print(f"  counteredBy 三元组 = {len(list(g.objects(None, PVE.counteredBy)))}")
print(f"  bossTrait 有字面量 = {len(set(g.subjects(PVE.bossTrait, None)))}")
print(f"  bannedPet = {len(list(g.objects(None, PVE.bannedPet)))}")
struct = ["bossHp","hasTypeCombination","clearsBuff","stealsBuff","clearsPP","turnFixedDamage","rawCap",
          "immunePanelOver","shield","multiLife","immuneSpecial","immunePhysical","onlyCrit","alwaysCrit",
          "selfBuffPerTurn","debuffUsPerTurn","control","dodge","rawCapMode"]
for p in struct:
    pr = PVE[p]
    print(f"    {p:16s} = {len(set(g.subjects(pr, None)))}")

# 宠物库
pet = set(g.subjects(RDF.type, SEER.Pet))
print(f"\nPet 个体 = {len(pet)}")
print(f"  hasRole 覆盖 = {len(set(g.subjects(PVE.hasRole, None)) & pet)}/{len(pet)}")
print(f"  hasSkill = {len(set(g.subjects(SEER.hasSkill, None)) & pet)}")