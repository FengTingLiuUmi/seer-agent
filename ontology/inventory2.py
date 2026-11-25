# -*- coding: utf-8 -*-
from rdflib import Graph, RDF, OWL, RDFS, Namespace, SKOS
SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
g = Graph()
g.parse(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-factor-kb\ontology\seer-all.owl", format="xml")

def ln(u): return str(u).split("#")[-1]

print("counters 三元组 =", len(list(g.triples((None, SEER.counters, None)))))
print("resisted 三元组 =", len(list(g.triples((None, SEER.resisted, None)))))
print("immune 三元组 =", len(list(g.triples((None, SEER.immune, None)))))

for p in [SEER.bossEffective, SEER.pveEffective]:
    true = [s for s, _, o in g.triples((None, p, None)) if str(o).lower() == "true"]
    print(f"{ln(p)} true = {len(true)}")

enemies = set(g.subjects(RDF.type, PVE.Enemy))
print("Enemy 有 hasTypeCombination =", len([e for e in enemies if (e, SEER.hasTypeCombination, None) in g]))
pets = set(g.subjects(RDF.type, SEER.Pet))
print("Pet 有 hasTypeCombination =", len([p for p in pets if (p, SEER.hasTypeCombination, None) in g]))
print("Pet 有 hasRole =", len([p for p in pets if (p, PVE.hasRole, None) in g]))
print("Pet 有 hasSkill =", len([p for p in pets if (p, SEER.hasSkill, None) in g]))
print("altLabel 总数 =", len(list(g.triples((None, SKOS.altLabel, None)))))
print("SkillEffect 有 effectInfo =", len(list(g.triples((None, SEER.effectInfo, None)))))
print("SkillEffect 有 effectTypeOf =", len(list(g.triples((None, SEER.effectTypeOf, None)))))
print("Skill 有 bossEffective 相关(任意) =", len([s for s in g.subjects(None, None) if 'skillfx' in str(s) and (s, SEER.bossEffective, None) in g]))