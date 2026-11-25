# -*- coding: utf-8 -*-
"""kb_gap.py —— 量化「因子关文档里被点名的精灵，本体是否有技能/魂印数据」。

用法（workdir=workspace 根）：
    python seer-factor-kb/ontology/kb_gap.py [--json out.json]

遍历 kb/docs/*/*.json 的 stages[].strategies[].pets，按 rdfs:label / skos:altLabel
解析到本体精灵，统计：解析不到（NOT_IN_KB）／有节点但 0 技能／有技能无魂印。
只读。
"""
import io
import json
import os
import sys
from collections import defaultdict

from rdflib import Graph, Namespace, RDF, RDFS

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
SEER = Namespace("http://example.org/seer#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def main():
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]
    g = Graph()
    g.parse(os.path.join(HERE, "seer-all.owl"), format="xml")
    idx = {}
    # 顺序要紧：`tool_nick` 先扫 skos:altLabel、再回退 rdfs:label，这里必须同序。
    # 反过来的话「咤克斯」会被解析成基础形态 pet_2648，而 PVE 口径指的是
    # 魔王·咤克斯 pet_3194（altLabel），统计出来的「风险」全是假的。
    for pred in (SKOS.altLabel, RDFS.label):
        for p in g.subjects(RDF.type, SEER.Pet):
            for lb in g.objects(p, pred):
                idx.setdefault(str(lb).strip(), p)
    docs = os.path.join(ROOT, "kb", "docs")
    used = defaultdict(set)
    for fac in sorted(os.listdir(docs)):
        fp = os.path.join(docs, fac)
        if not os.path.isdir(fp):
            continue
        for fn in sorted(os.listdir(fp)):
            if not fn.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(fp, fn), encoding="utf-8"))
            except Exception:
                continue
            did = d.get("doc_id") or f"{fac}#{fn[:-5]}"
            for st in d.get("stages") or []:
                for sp in st.get("strategies") or []:
                    for pn in sp.get("pets") or []:
                        used[pn].add(did)
    notin, zero, nosm = [], [], []
    for pn in sorted(used, key=lambda x: (-len(used[x]), x)):
        p = idx.get(pn)
        if p is None:
            notin.append((pn, len(used[pn])))
            continue
        nsk = len(list(g.objects(p, SEER.hasSkill)))
        # 魂印在数据里是反向挂的：soulmark seer:affectsPet pet（见 seer-effects-abox.ttl），
        # 正向 seer:hasSoulmark 只有早期 PVE 精灵池留下的 72 条，不能用来判覆盖率。
        nsm = len(list(g.subjects(SEER.affectsPet, p)))
        rec = (pn, str(p).split("#")[-1], len(used[pn]))
        if nsk == 0:
            zero.append(rec)
        elif nsm == 0:
            nosm.append(rec)
    print(f"# 文档被点名精灵 {len(used)} 只 | 解析不到 {len(notin)} | 无技能 {len(zero)} | 无魂印 {len(nosm)}")
    print("\n## NOT_IN_KB（本体里没有这个名字/简称）")
    for n, c in notin:
        print(f"  {n}  （{c} 篇）")
    print("\n## 有节点但 0 技能（需 --pet-id 回填）")
    for n, pid, c in zero:
        print(f"  {pid}\t{n}\t{c} 篇")
    print("\n## 有技能无魂印")
    for n, pid, c in nosm:
        print(f"  {pid}\t{n}\t{c} 篇")

    # 第三类缺口：技能清单「不全」。0 技能能查出来，缺一半查不出来
    # （实例：星光·鲁斯王 本体 12 条 vs API 17 条，缺的正是反弹技「克制」）。
    # 用 onto_fill 的磁盘缓存比对数量，不额外走网络；缓存里没有的宠物跳过。
    partial = []
    cachep = os.path.join(HERE, "skill-cache.json")
    if os.path.exists(cachep):
        cache = json.load(open(cachep, encoding="utf-8"))
        for pn in sorted(used):
            p = idx.get(pn)
            if p is None:
                continue
            pid = str(p).split("#")[-1].split("_")[-1]
            api = cache.get(f"https://api.seerapi.com/v1/pet/{pid}")
            if not api:
                continue
            want = len(api.get("skill") or [])
            have = len(list(g.objects(p, SEER.hasSkill)))
            if want and have < want:
                partial.append((pn, pid, have, want))
        # 同名多行合并成一行
        agg = {}
        for pn, pid, have, want in partial:
            k = (pid, have, want)
            agg.setdefault(k, []).append(pn)
        print(f"\n## 技能清单不全（本体 < API；需再跑 onto_fill --pet-ids）  {len(agg)} 只")
        for (pid, have, want), nms in sorted(agg.items(), key=lambda x: (x[0][2] - x[0][1]), reverse=True):
            print(f"  {pid}\t{have}/{want}\t{', '.join(nms[:3])}")

    if out_json:
        json.dump({"notin": notin, "zero": zero, "nosm": nosm},
                  open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nwrote", out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())