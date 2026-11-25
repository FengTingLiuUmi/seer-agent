# -*- coding: utf-8 -*-
import os
from rdflib import Graph, RDF, Namespace

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

g = Graph()
g.parse(f"{HERE}/seer-boss-abox.ttl", format="turtle")

factors = set(g.subjects(RDF.type, SEER.Factor))
stages = set(g.subjects(RDF.type, SEER.FactorStage))
enemies = set(g.subjects(RDF.type, PVE.Enemy))
print(f"Factor={len(factors)} FactorStage={len(stages)} Enemy={len(enemies)}")

# 玖莉娜 的关卡应覆盖 hard + normal 两档，共 10 关
j = SEER.factor_jiulina
print("玖莉娜 hasStage:")
for s in sorted(g.objects(j, SEER.hasStage), key=lambda x: str(x)):
    print("  ", str(s).rsplit('#',1)[-1])

# 展示所有因子 -> 各难度关数
from collections import Counter
cnt = Counter()
for f in factors:
    for s in g.objects(f, SEER.hasStage):
        d = next((str(o).rsplit('#',1)[-1] for o in g.objects(s, PVE.difficulty)), "?")
        cnt[(str(f).rsplit('#',1)[-1], d)] += 1
print("因子×难度 覆盖（出现不同难度的因子才会多行）:")
for f in sorted(factors, key=lambda x: str(x)):
    fn = str(f).rsplit('#',1)[-1]
    ds = sorted({d for (ff,d) in cnt if ff==fn})
    if len(ds) > 1 or any(d != 'diff_hard' for d in ds):
        print("  ", fn, "<-", ds, "关数", [cnt[(fn,d)] for d in ds])