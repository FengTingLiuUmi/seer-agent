# -*- coding: utf-8 -*-
"""解析校验 seer-game.ttl / seer-pve.ttl（用 rdflib，仅查语法+统计三元组数）。用法：python validate.py"""
import os
from rdflib import Graph

HERE = os.path.dirname(os.path.abspath(__file__))
for f in ("seer-game.ttl", "seer-pve.ttl", "seer-pve-alias.ttl"):
    g = Graph()
    g.parse(os.path.join(HERE, f), format="turtle")
    print("OK", f, "triples =", len(g))