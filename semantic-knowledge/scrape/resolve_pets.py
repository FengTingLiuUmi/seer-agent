# -*- coding: utf-8 -*-
"""把合并抽取结果里的全部「pets」令牌对回本体（别名/标签/id），
拆成 已认识(known) / 待补充(missing)，供补本体缺失精灵用。
运行：PYTHONPATH=.pylibs PYTHONUTF8=1 python resolve_pets.py
输入：scrape/factors-extracted.json（merge_extract.py 产物）
输出：scrape/pets-resolved.json = {known:{token:{id,label}}, missing:[token]}
"""
import os, re, json, sys

ONT = "C:/Users/kmdbn/Documents/deepseek-harness/default-workspace/seer/seer-factor-kb/ontology".replace("/", "\\")
sys.path.insert(0, ONT.replace("\\", "/"))
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

from rdflib import Graph, RDF, RDFS, Namespace, SKOS

SEER = Namespace("http://example.org/seer#")
G = Graph()
G.parse(f"{HERE}/../ontology/seer-all.owl", format="xml")

def ln(u): return str(u).rsplit("#", 1)[-1]
def label(node):
    for o in G.objects(node, RDFS.label):
        return str(o)
    return ln(node)
def id_of(node):
    v = G.value(node, SEER.seerapiId)
    return str(v) if v is not None else None
def core_name(s):
    return re.sub(r"[（(].*?[)）]", "", s).replace("·", "").replace(" ", "").strip()

# 预先建立 名字/别名/id → pet 索引
pets = list(G.subjects(RDF.type, SEER.Pet))
exact = {}   # normalized token -> (id,label)
contains = []  # (id,label,normalized_label)

for p in pets:
    pid, lab = id_of(p), label(p)
    entry = (pid, lab)
    for t in {lab, core_name(lab), pid}:
        if t:
            exact.setdefault(t, entry)
    for o in G.objects(p, SKOS.altLabel):
        t = str(o)
        local = [t, core_name(t)]
        for x in local:
            if x:
                exact.setdefault(x, entry)
    contains.append((pid, lab, core_name(lab)))

def resolve(tok):
    t = core_name(tok)
    if not t:
        return None
    if t in exact:
        return exact[t]
    # 双向包含（鲁斯王 vs 星光鲁斯王）
    for pid, lab, cn in contains:
        if t in cn or (cn and cn in t):
            return (pid, lab)
    return None

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "factors-extracted.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "pets-resolved.json"
    if not os.path.isabs(src):
        src = f"{HERE}/{src}"
    if not os.path.isabs(out):
        out = f"{HERE}/{out}"
    data = json.load(open(src, encoding="utf-8"))
    tokens = set()
    for e in data:
        for s in e.get("stages", []):
            for p in s.get("pets", []):
                tokens.add(str(p))
    known, missing = {}, []
    for tok in sorted(tokens):
        r = resolve(tok)
        if r:
            known.setdefault(tok, {"id": r[0], "label": r[1]})
        else:
            missing.append(tok)
    json.dump({"known": known, "missing": missing}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"distinct pets 令牌 = {len(tokens)}")
    print(f"  已认识 = {len(known)}，待补充(缺) = {len(missing)}")
    print("待补充令牌：", missing)


if __name__ == "__main__":
    main()