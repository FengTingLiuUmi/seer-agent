# -*- coding: utf-8 -*-
"""ingest_status.py —— 从 kb/docs 派生「异常状态 ← Boss 关卡/物种」关系，写入 seer-status-abox.ttl。

分工：
  seer-status.ttl      = 定义层（类/属性/43 个状态的官方字段），手工维护，本脚本**不碰**。
  seer-status-abox.ttl = 派生层（本脚本生成，幂等）：seer:inflictedByEnemy / seer:inflictedByPet /
                         seer:bossStageCount。每次运行整体重写，产物按 IRI 排序，重复跑逐字节一致。

数据来源：
  kb/docs/<因数>/<难度>.json 的 stages[].traits（B 级：论坛/攻略文本）
  ontology/seer-factors-abox.ttl（已有 205 个 Factor / 1162 个 FactorStage / pve:Enemy 的 bossSpecies）
只做「文本命中 → 实体链接」，不产出任何数值/概率。

用法（工作区根）：
    $env:PYTHONPATH="<ws>/seer-factor-kb/.pylibs"; $env:PYTHONUTF8="1"
    F:\\python\\py310\\python.exe seer-factor-kb\\ontology\\ingest_status.py
    ... --dry-run   只统计不写盘
"""
import glob
import json
import os
import sys

from rdflib import Graph, Namespace, RDF, RDFS, Literal

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..")).replace("\\", "/")
DOCS = f"{HERE}/../kb/docs"
FACTORS_ABOX = f"{HERE}/seer-factors-abox.ttl"
STATUS_TTL = f"{HERE}/seer-status.ttl"
OUT = f"{HERE}/seer-status-abox.ttl"
BASE = f"{HERE}/seer-game.ttl"

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")

DIFF = {"简单": "easy", "困难": "normal", "地狱": "hard",
        "easy": "easy", "normal": "normal", "hard": "hard"}


def load_statuses():
    """从 seer-status.ttl 取 (本地名, 中文名, seerapiId)。只读，不写。"""
    g = Graph()
    g.parse(STATUS_TTL, format="turtle")
    out = []
    for s in g.subjects(RDF.type, SEER.StatusAilment):
        name = g.value(s, SEER.statusName)
        sid = g.value(s, SEER.seerapiId)
        if name is None:
            continue
        out.append((str(s).rsplit("#", 1)[-1], str(name), str(sid) if sid else ""))
    out.sort()
    return out


def load_stage_index():
    """(因子中文名, easy/normal/hard, 关号) → (stage IRI, enemy IRI)；enemy IRI → 物种 pet IRI。

    注意：不能用「stage 反查 Factor」——seer-factors-abox.ttl 里同一 Factor 的 hasStage
    并不总是把全部难度都列全（如 佩洛瑟斯 只列了 normal，hard 关仍存在为独立个体）。
    因此改为「因子中文名 → 因子 slug → 拼 stage IRI → 校验存在」，稳定且不依赖 hasStage 完整性。
    """
    g = Graph()
    g.parse(FACTORS_ABOX, format="turtle")
    by_label = {}
    for f in g.subjects(RDF.type, SEER.Factor):
        lab = g.value(f, RDFS.label)
        if lab:
            slug = str(f).rsplit("#", 1)[-1]
            if slug.startswith("factor_"):
                slug = slug[len("factor_"):]
            by_label[str(lab)] = slug

    stages = {}
    for st in g.subjects(RDF.type, SEER.FactorStage):
        n = g.value(st, PVE.stageNumber)
        d = g.value(st, PVE.difficulty)
        en = g.value(st, PVE.hasEnemy)
        if n is None or d is None or en is None:
            continue
        diff = str(d).rsplit("#", 1)[-1].replace("diff_", "")
        # stage IRI 形如 seer:stage_<slug>_<diff>_<n>，拿来和 docs 的 (因子,难度,关号) 对齐
        local = str(st).rsplit("#", 1)[-1]
        tail = f"_{diff}_{int(n)}"
        if not local.startswith("stage_") or not local.endswith(tail):
            continue
        slug = local[len("stage_"):-len(tail)]
        stages[(slug, diff, int(n))] = (st, en)

    index, enemy_species = {}, {}
    for (slug, diff, n), (st, en) in stages.items():
        index[(slug, diff, n)] = (st, en)
        sp = g.value(en, PVE.bossSpecies)
        if sp is not None:
            enemy_species[en] = sp
    return by_label, index, enemy_species


def load_docs():
    out = []
    for fp in sorted(glob.glob(f"{DOCS}/*/*.json")):
        if fp.endswith("catalog.json"):
            continue
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        fac = d.get("factor")
        diff = DIFF.get(d.get("difficulty"), "")
        if not fac or not diff:
            continue
        for st in d.get("stages", []):
            n = st.get("stage")
            traits = st.get("traits") or ""
            if n is None or not traits:
                continue
            out.append((fac, diff, int(n), traits))
    return out


def main():
    dry = "--dry-run" in sys.argv
    statuses = load_statuses()
    by_label, index, enemy_species = load_stage_index()
    docs = load_docs()

    print(f"[status] 个体 {len(statuses)}；因子(可映射) {len(by_label)}；关卡索引 {len(index)}；docs 关 {len(docs)}")

    # sid -> [(factorLabel, diff, stageNo, enemy|None, matchedText)]
    hits = {sid: [] for sid, _, _ in statuses}
    unlinked = 0
    for fac, diff, n, traits in docs:
        slug = by_label.get(fac)
        link = index.get((slug, diff, n)) if slug else None
        if link is None:
            for sid, name, _ in statuses:
                if name in traits:
                    hits[sid].append((fac, diff, n, None, name))
                    unlinked += 1
            continue
        st_iri, en_iri = link
        for sid, name, _ in statuses:
            if name in traits:
                hits[sid].append((fac, diff, n, en_iri, name))

    # ---- 生成 TTL（确定性：按 IRI 排序、固定缩进）----
    L = []
    L.append("# " + "=" * 68)
    L.append("# 派生文件：由 ontology/ingest_status.py 生成，请勿手改。")
    L.append("# 内容：异常状态 ←→ Boss 关卡/物种（来源 kb/docs/*/*.json 的 stages[].traits 文本命中）")
    L.append("# bossStageCount = docs 文本命中关数（含未能链接到本体关卡的那些，不虚增也不虚减）")
    L.append("# inflictedByEnemy / inflictedByPet 只写能解析到真实个体的（宁缺毋滥，不编 IRI）")
    L.append("# 重新生成：python seer-factor-kb/ontology/ingest_status.py")
    L.append("# " + "=" * 68)
    L.append("")
    L.append("@prefix seer: <http://example.org/seer#> .")
    L.append("@prefix pve:  <http://example.org/seer/pve#> .")
    L.append("@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .")
    L.append("")

    n_triples = 0
    for sid, name, api_id in statuses:
        rows = hits.get(sid, [])
        if not rows:
            continue
        enemies, pets = [], []
        for fac, diff, n, en, _ in rows:
            if en is None:
                continue
            if en not in enemies:
                enemies.append(en)
            sp = enemy_species.get(en)
            if sp is not None and sp not in pets:
                pets.append(sp)
        L.append(f"seer:{sid}")
        body = [f"    seer:bossStageCount {len(rows)}"]
        n_triples += 1
        for p in sorted(pets, key=str):
            body.append(f"    seer:inflictedByPet seer:{str(p).rsplit('#', 1)[-1]}")
            n_triples += 1
        for e in sorted(enemies, key=str):
            body.append(f"    seer:inflictedByEnemy pve:{str(e).rsplit('#', 1)[-1]}")
            n_triples += 1
        L.append(" ;\n".join(body) + " .")
        L.append("")
        print(f"  {name}({api_id}) 文本命中 {len(rows)} 关 / 已链接 {len(enemies)} 敌 / {len(pets)} 物种")

    text = "\n".join(L)
    if dry:
        print(f"[dry-run] 将写 {len(text)} 字符 / {n_triples} 三元组；未落盘")
        if unlinked:
            print(f"[note] {unlinked} 条命中落在本体未收录的因子/关卡上：计入 bossStageCount，但不写 IRI")
        return

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"[write] {OUT}  {n_triples} 三元组  {len(text)} 字符")
    if unlinked:
        print(f"[note] {unlinked} 条命中落在本体未收录的因子/关卡上：计入 bossStageCount，但不写 IRI")


if __name__ == "__main__":
    main()