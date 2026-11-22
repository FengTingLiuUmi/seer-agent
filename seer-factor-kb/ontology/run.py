# -*- coding: utf-8 -*-
"""
赛尔号因子 PVE 本体 —— 框架支持演示脚本（rdflib）
加载 seer-onto.ttl：校验语法 → 统计 → SPARQL/图查询 → 规则前向链（衍生推理）→ 导出推断图。
用法：python run.py
"""
import sys, os
from rdflib import Graph, Namespace, RDF, RDFS, OWL

EX = Namespace("http://example.org/seer-factor#")
HERE = os.path.dirname(os.path.abspath(__file__))
ONTO = os.path.join(HERE, "seer-onto.ttl")
INFERRED = os.path.join(HERE, "seer-onto-inferred.ttl")

g = Graph()
try:
    g.parse(ONTO, format="turtle")
except Exception as e:
    print("解析失败：", repr(e))
    sys.exit(1)

def label(node, fallback=True):
    n = next(iter(g.objects(node, RDFS.label)), None)
    if n is not None:
        return str(n)
    return str(node).rsplit("#", 1)[-1] if fallback else str(node)

def ptype(cls):
    return set(g.subjects(RDF.type, EX[cls]))

print("=== 语法校验通过，图规模 ===")
print("三元组:", len(g))
for c in ["Pet","Skill","Soulmark","Boss","Stage","Mechanism","Strategy","Config","Buff","Equipment","Difficulty","Reward"]:
    print(f"  {c}: {len(ptype(c))}")
print("  ObjectProperty:", len(set(g.subjects(RDF.type, OWL.ObjectProperty))))
print("  DatatypeProperty:", len(set(g.subjects(RDF.type, OWL.DatatypeProperty))))

print("\n=== [1] 精灵与定位（已录） ===")
for p in sorted(ptype("Pet"), key=lambda x: label(x)):
    roles = [label(r) for r in g.objects(p, EX.playsRole)]
    sid = next((str(o) for o in g.objects(p, EX.seerapiId)), "-")
    print(f"  {label(p)}  | 定位={roles}  | seerapiId={sid}")

print("\n=== [2] 属性克制：谁克「机械」 ===")
for e in g.subjects(EX.counters, EX["机械"]):
    print("  ", label(e))

print("\n=== [3] 机制 → 推荐打法（事实断言） ===")
for m in sorted(ptype("Mechanism"), key=lambda x: label(x)):
    ss = [label(s) for s in g.objects(m, EX.recommendedStrategy)]
    if ss:
        print(f"  {label(m)} -> {ss}")

print("\n=== [4] 衍生推理：Boss → 推荐打法 / 推荐配置（前向链） ===")
for b in sorted(ptype("Boss"), key=lambda x: label(x)):
    strats, confs = set(), set()
    for m in g.objects(b, EX.hasMechanism):
        strats.update(label(s) for s in g.objects(m, EX.recommendedStrategy))
        # Buff 轴：机制施加的效果 → 克制该效果的打法
        for buf in g.objects(m, EX.hasBuff):
            strats.update(label(s) for s in g.subjects(EX.countersBuff, buf))
        # 装备轴：机制 → 配置模板
        if m == EX["裸伤上限"]: confs.add(label(EX["cfg_站场套"]))
        if m == EX["面板免疫"]: confs.add(label(EX["cfg_弹伤套"]))
        if m == EX["护盾"]:     confs.add(label(EX["cfg_弹伤套"]))
        if m == EX["控场"]:     confs.add(label(EX["cfg_强攻套"]))
    print(f"  {label(b)}")
    print(f"      打法={sorted(strats)}")
    print(f"      配置={sorted(confs)}")

print("\n=== [5] 被Ban→替代链（substitutesFor 传递闭包） ===")
sub = {p: set(x for x in g.objects(p, EX.substitutesFor)) for p in ptype("Pet")}
def closure(p, seen=()):
    if p in seen: return set()
    out = set()
    for n in sub.get(p, ()):
        out.add(n); out |= closure(n, seen + (p,))
    return out

for stage in sorted(ptype("Stage"), key=lambda x: label(x)):
    banned = [label(b) for b in g.objects(stage, EX.bannedPet)]
    if not banned:
        continue
    print(f"  {label(stage)} 禁用={banned}")
    for b in g.objects(stage, EX.bannedPet):
        alts = set()
        for p in sub:
            if b in closure(p):
                alts.add(label(p))
        print(f"      替代 {label(b)} <- {sorted(alts)}")

# 导出推断结果（把衍生 triples 写进副本，便于 Protégé 查看）
print("\n=== 导出推断图 -> seer-onto-inferred.ttl ===")
g2 = Graph()
for t in g:
    g2.add(t)
for b in ptype("Boss"):
    for m in g.objects(b, EX.hasMechanism):
        for s in g.objects(m, EX.recommendedStrategy):
            g2.add((b, EX.recommendedStrategy, s))
        for buf in g.objects(m, EX.hasBuff):
            for s in g.subjects(EX.countersBuff, buf):
                g2.add((b, EX.recommendedStrategy, s))
        if m == EX["裸伤上限"]: g2.add((b, EX.recommendedConfig, EX["cfg_站场套"]))
        if m in (EX["面板免疫"], EX["护盾"]): g2.add((b, EX.recommendedConfig, EX["cfg_弹伤套"]))
        if m == EX["控场"]: g2.add((b, EX.recommendedConfig, EX["cfg_强攻套"]))
g2.serialize(destination=INFERRED, format="turtle")
print("  已写入", INFERRED, "（新增推断三元组后共", len(g2), "条）")