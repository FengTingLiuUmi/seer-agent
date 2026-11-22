# -*- coding: utf-8 -*-
"""修复因子关 IRI 冲突：stage/enemy 的本地名补上难度档。
问题：玖莉娜同时在 地狱(scrape-A) 与 困难(scrape-B) 用同一组
      stage_jiulina_N / enemy_jiulina_N，合并时把困难档挤掉了。
修法：先**逐文件**各自按本文件内 stage 的 pve:difficulty 重命名，再合并。
      新 IRI：seer:stage_<slug>_<diff>_<N> 与 pve:enemy_<slug>_<diff>_<N>。
"""
import os
from rdflib import Graph, RDF, RDFS, Namespace
from rdflib.namespace import XSD

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

SRC = ["seer-boss-abox.ttl", "seer-boss-scrape-A.ttl.bak", "seer-boss-scrape-B.ttl.bak"]
DIFF = {str(PVE.diff_hard): "hard", str(PVE.diff_normal): "normal", str(PVE.diff_easy): "easy"}


def rename_in_file(path):
    g = Graph()
    g.parse(path, format="turtle")

    stage_info = {}
    for s in set(g.subjects(RDF.type, SEER.FactorStage)):
        diffs = [DIFF[str(o)] for o in g.objects(s, PVE.difficulty) if str(o) in DIFF]
        ns = [str(o) for o in g.objects(s, PVE.stageNumber)]
        assert len(set(diffs)) == 1, (s, diffs)
        diff = diffs[0]
        n = ns[0]
        local = str(s).rsplit("#", 1)[-1]
        assert local.startswith("stage_"), local
        slug, tail = local[len("stage_"):].rsplit("_", 1)
        assert tail == n, (s, tail, n)
        stage_info[s] = (slug, diff, n)

    rename = {}
    for s, (slug, diff, n) in stage_info.items():
        rename[s] = SEER[f"stage_{slug}_{diff}_{n}"]
        for e in g.objects(s, PVE.hasEnemy):
            rename[e] = PVE[f"enemy_{slug}_{diff}_{n}"]

    g2 = Graph()
    for s, p, o in g:
        g2.add((rename.get(s, s), p, rename.get(o, o)))
    return g2


def main():
    merged = Graph()
    merged.bind("seer", SEER)
    merged.bind("pve", PVE)
    merged.bind("rdfs", RDFS)
    merged.bind("xsd", XSD)
    for f in SRC:
        p = f"{HERE}/{f}"
        if os.path.exists(p):
            g2 = rename_in_file(p)
            for t in g2:
                merged.add(t)
            print("renamed+merged", f, f"({len(g2)} 三元组)")

    out = f"{HERE}/seer-boss-abox.ttl"
    merged.serialize(out, format="turtle")
    print(f"写出 {out}，共 {len(merged)} 三元组")


if __name__ == "__main__":
    main()