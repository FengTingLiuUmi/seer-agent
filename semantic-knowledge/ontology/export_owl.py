# -*- coding: utf-8 -*-
"""把 seer-game.ttl / seer-pve.ttl 转成 owlready2 + Protégé 友好读的 RDF/XML（.owl）。
源码仍是 .ttl；.owl 是生成产物。
会顺带把 ABox 个体标注为 owl:NamedIndividual，owlready2 才能 recognized 它们。
用法：python export_owl.py（需要 rdflib）
"""
import os
from rdflib import Graph, RDF, OWL

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [("seer-game.ttl", "seer-game.owl"), ("seer-pve.ttl", "seer-pve.owl")]

for src, dst in PAIRS:
    g = Graph()
    g.parse(os.path.join(HERE, src), format="turtle")
    classes = set(g.subjects(RDF.type, OWL.Class))
    n = 0
    for s, o in list(g.subject_objects(RDF.type)):
        if o in classes:
            g.add((s, RDF.type, OWL.NamedIndividual))
            n += 1
    out = os.path.join(HERE, dst)
    g.serialize(out, format="xml")
    print("OK %s -> %s  个体=%d  三元组=%d" % (src, dst, n, len(g)))