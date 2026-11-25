# -*- coding: utf-8 -*-
"""把「因子×难度」各关策略涉及的精灵，与玩家缓存做持有匹配（名字维度）。

策略 pets 是物种名，缓存也带 name；直接按名命中。名字未归一（未经过 nick/alias 消歧），
所以个别社区简称/变体会误报为「缺」——正式判「缺」要再过本体 label/altLabel 兜底。

运行：python player/match_factor.py [因子] [难度] [米米号]
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import player_cache as PC  # noqa: E402

KB = os.path.abspath(os.path.join(HERE, "..", "kb", "docs"))
KB_ROOT = os.path.abspath(os.path.join(HERE, ".."))
for _sub in (os.path.join(KB_ROOT, ".pylibs"), os.path.join(KB_ROOT, "ontology")):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)
DEFAULT_MIMI = "753949294"


_OWL = None


def _owl():
    global _OWL
    if _OWL is None:
        from rdflib import Graph
        g = Graph()
        g.parse(os.path.join(KB_ROOT, "ontology", "seer-all.owl"), format="xml")
        _OWL = g
    return _OWL


def _resolve_aliases(name):
    """本体兜底：把社区简称精确解析成 seerapiId 列表（altLabel/label/id 精确，不做子串）。

    攻略 pets 常写简称（如「克罗」「咤克斯」），缓存里是完整名（神寂·克罗诺斯 / 魔王·咤克斯），
    只按名字精确匹配会误报「缺」。这里用本体 altLabel/label/seerapiId 精确消歧归一到 id。
    """
    try:
        from rdflib import SKOS, RDFS, Namespace
        g = _owl()
        SEER = Namespace("http://example.org/seer#")
        ids, seen = [], set()
        for s, o in g.subject_objects(SKOS.altLabel):
            if str(o) == name:
                v = g.value(s, SEER.seerapiId)
                if v is not None and str(v) not in seen:
                    seen.add(str(v))
                    ids.append(str(v))
        if not ids:
            for s in g.subjects(None, None):
                if not str(s).rsplit("#", 1)[-1].startswith("pet_"):
                    continue
                v = g.value(s, SEER.seerapiId)
                vid = str(v) if v is not None else None
                if vid == name and vid and vid not in seen:
                    seen.add(vid)
                    ids.append(vid)
                for lbl in g.objects(s, RDFS.label):
                    if str(lbl) == name and vid and vid not in seen:
                        seen.add(vid)
                        ids.append(vid)
        return ids
    except Exception:
        return []


def main():
    factor = sys.argv[1] if len(sys.argv) > 1 else "瓦坎"
    difficulty = sys.argv[2] if len(sys.argv) > 2 else "地狱"
    mimi = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MIMI

    doc_path = os.path.join(KB, factor, f"{difficulty}.json")
    if not os.path.exists(doc_path):
        print(f"未找到 {factor}#{difficulty} 的 SSOT 文档")
        return 1
    with open(doc_path, encoding="utf-8") as f:
        doc = json.load(f)

    conn = PC.connect()

    distinct, seen = [], set()
    for st in doc.get("stages", []):
        for sg in st.get("strategies", []):
            for p in sg.get("pets", []):
                if p not in seen:
                    seen.add(p)
                    distinct.append(p)

    print(f"{factor}#{difficulty}  策略涉及精灵 {len(distinct)} 只（去重）")
    print("=" * 46)
    owned, missing = [], []
    for p in distinct:
        has = PC.has_species_by_name(conn, mimi, p)
        cnt = PC.count_species_by_name(conn, mimi, p)
        sid = PC.species_id_by_name(conn, mimi, p)
        note = ""
        if not has:
            for cid in _resolve_aliases(p):
                if PC.has_species(conn, mimi, cid):
                    has, sid = True, cid
                    cnt = PC.count_species(conn, mimi, cid)
                    note = f"（本体消歧：{p} → species_id {cid}）"
                    break
        tag = "有" if has else "缺"
        print(f"[{tag}] {p}  只数={cnt}  species_id={sid or '-'}{note}")
        (owned if has else missing).append(p)
    print("=" * 46)
    print(f"持有 {len(owned)}  缺失 {len(missing)}")
    if missing:
        print("缺失:", "、".join(missing))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())