# -*- coding: utf-8 -*-
"""onto_del.py —— 从回填层删除一个实体（默认按技能名，删技能+其效果节点+hasSkill 边）

只动 seer-miss-abox.ttl（回填层），不碰手写的 TBox / 生成的全量 ABox。
删完自动跑 sync.py --merge-only，让 seer-all.owl 生效。

用法：
  python onto_del.py --skill "能量"
  python onto_del.py --skill-id 11274
  python onto_del.py --iri "http://example.org/seer#skill_11274"
  python onto_del.py --skill "能量" --dry
"""
import argparse
import os
import subprocess
import sys

from rdflib import Graph, Namespace, RDF

SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "seer-miss-abox.ttl")


def resolve(g, name, sid, iri):
    from rdflib.namespace import RDFS
    if iri:
        return SEER[iri.rsplit("#", 1)[-1]]
    for s in g.subjects(RDF.type, SEER.Skill):
        lb = str(g.value(s, RDFS.label) or "")
        if (sid and str(g.value(s, SEER.seerapiId)) == str(sid)) or (name and lb == name):
            return s
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill")
    ap.add_argument("--skill-id", type=int)
    ap.add_argument("--iri")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if not any([a.skill, a.skill_id, a.iri]):
        print(__doc__)
        return 2
    if not os.path.exists(SRC):
        print("没有回填层文件:", SRC)
        return 3

    g = Graph()
    g.parse(SRC, format="turtle")
    before = len(g)
    target = resolve(g, a.skill, a.skill_id, a.iri)
    if target is None:
        print("回填层里找不到这个实体")
        return 3

    # 收集要删的节点：技能本身 + 它的效果节点
    doomed = {target}
    for be in list(g.objects(target, SEER.hasSkillEffect)):
        doomed.add(be)

    removed = 0
    for node in doomed:
        for t in list(g.triples((node, None, None))):
            g.remove(t)
            removed += 1
        for t in list(g.triples((None, None, node))):
            g.remove(t)
            removed += 1

    print(f"删除 {target.rsplit('#', 1)[-1]}：{len(doomed)} 个节点 / {removed} 条三元组（{before} -> {len(g)}）")
    if a.dry:
        print("dry-run：未写文件")
        return 0
    g.serialize(destination=SRC, format="turtle")
    print("已写回", SRC)
    r = subprocess.run([sys.executable, os.path.join(HERE, "sync.py"), "--merge-only"],
                       capture_output=True, text=True, encoding="utf-8")
    for line in (r.stdout or "").splitlines():
        if "总三元组" in line or "不一致" in line:
            print("  ", line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())