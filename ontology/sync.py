# -*- coding: utf-8 -*-
"""一键同步：全量 ABox + PVE 精选 ABox + 导出 .owl + 合并一致性体检。
用法：
    python sync.py             # 全量同步（--full 耗时很长）
    python sync.py --no-full   # 跳过全量，只跑 PVE + 导出 + 体检（本地快速验证）
    python sync.py --merge-only # 只重跑合并 + NamedIndividual + HermiT（ABox 已单独生成好时用）
依赖：rdflib（PYTHONPATH 含 .pylibs 或已全局）；owlready2；推理需 java 在 PATH。
注意：seer-gear-abox.ttl（套装/装备/称号/性格）由 ingest_gear.py 单独生成，本脚本不含该步。
注意：**任何重建（含 --merge-only）都会改变 seer-all.owl，使 _mcp_baseline.json 失效**；
      重建后必须用 status_selftest.py --baseline 重采基线，否则 --check 的回归对比全是假差异。
"""
import os, sys, shutil, time
from rdflib import Graph, RDF, OWL

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
FILES = ["seer-game.ttl", "seer-onto.ttl", "seer-status.ttl", "seer-pve.ttl", "seer-pve-alias.ttl", "seer-pve-roles.ttl",
         "seer-game-abox.ttl", "seer-typechart.ttl", "seer-pve-abox.ttl", "seer-pve-supp.ttl",
         "seer-gear-abox.ttl", "seer-boss-abox.ttl", "seer-factors-abox.ttl",
         "seer-status-abox.ttl", "seer-effects-abox.ttl", "seer-miss-abox.ttl"]

KEEP_BACKUPS = 5   # 保留最近 5 次备份


def backup():
    """合并前给全部源 ttl 做一次快照，防止手改/脚本误伤后无法回滚。

    教训（2026-11-25）：用正则批量改 seer-onto.ttl 时误伤语法，且无 git 备份，
    最后只能从 seer-all.owl 快照重建，行内注释全部丢失。
    """
    todo = [f for f in FILES if os.path.exists(f"{HERE}/{f}")]
    if not todo:
        return
    dst = f"{HERE}/.bak/{time.strftime('%Y%m%d-%H%M%S')}"
    os.makedirs(dst, exist_ok=True)
    for f in todo:
        shutil.copy2(f"{HERE}/{f}", f"{dst}/{f}")
    # 只留最近 KEEP_BACKUPS 份
    root = f"{HERE}/.bak"
    stamps = sorted((d for d in os.listdir(root) if os.path.isdir(f"{root}/{d}")), reverse=True)
    for old in stamps[KEEP_BACKUPS:]:
        shutil.rmtree(f"{root}/{old}", ignore_errors=True)
    print(f"    备份 {len(todo)} 个 ttl -> .bak/{os.path.basename(dst)}")


def run(cmd):
    print("\n==> " + cmd, flush=True)
    print("    exit =", os.system(cmd))


def merge_check():
    print("\n==> 合并 TBox + ABox -> seer-all.owl")
    backup()
    g = Graph()
    for f in FILES:
        p = f"{HERE}/{f}"
        if os.path.exists(p):
            g.parse(p, format="turtle")
            print("    +", f)
    classes = set(g.subjects(RDF.type, OWL.Class))
    n = 0
    for s, o in list(g.subject_objects(RDF.type)):
        if o in classes:
            g.add((s, RDF.type, OWL.NamedIndividual))
            n += 1
    # 合并文件已自包含，去掉 owl:imports，否则 owlready2 会去下载 import 的 IRI
    for s, o in list(g.subject_objects(OWL.imports)):
        g.remove((s, OWL.imports, o))
    merged = f"{HERE}/seer-all.owl"
    g.serialize(merged, format="xml")
    print(f"    NamedIndividual={n}  总三元组={len(g)}")

    print("==> owlready2 + HermiT 一致性")
    try:
        from owlready2 import get_ontology, sync_reasoner_hermit, default_world
        onto = get_ontology(merged).load()
        with onto:
            sync_reasoner_hermit()
        inc = list(default_world.inconsistent_classes())
        print("    HermiT 完成；不一致类:", [c.name for c in inc] or "无（本体一致）")
    except Exception as e:
        print("    推理跳过:", str(e)[:200])


def main():
    if "--merge-only" in sys.argv:
        merge_check()
        return
    if "--no-full" not in sys.argv:
        run(f'python "{HERE}/ingest.py" --full')
    run(f'python "{HERE}/ingest.py" --pve')
    run(f'python "{HERE}/export_owl.py"')
    merge_check()


if __name__ == "__main__":
    main()