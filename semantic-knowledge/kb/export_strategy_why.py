# -*- coding: utf-8 -*-
"""export_strategy_why.py —— 把已清洗的逐策略 why 回写进覆盖表。

为什么：`kb/docs/*.json` 里 strategies[].why 是 split_docs 的产物，重跑会被
attrib_why() 从「关级 why」重新切句覆盖。清洗过的那批必须落到
`scrape/factors-strategy-why.json`（键 = 因子|难度 / 关号 / plan 归一），
refactor_strategies.py 会优先用它。

用法（workdir=seer-factor-kb，或从外面传 --root）：
    python kb/export_strategy_why.py            # 合并写入（幂等）
    python kb/export_strategy_why.py --dry      # 只看会写多少条
    python kb/export_strategy_why.py --only 墟婆 图特摩斯   # 只导出指定因子
"""
import argparse
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRAPE = os.path.join(ROOT, "scrape")
DOCS = os.path.join(HERE, "docs")
OUT = os.path.join(SCRAPE, "factors-strategy-why.json")


def canon(t):
    return re.sub(r"\s+", "", str(t or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()

    store = {}
    if os.path.exists(OUT):
        store = json.load(open(OUT, encoding="utf-8"))

    added = 0
    for fac in sorted(os.listdir(DOCS)):
        fp = os.path.join(DOCS, fac)
        if not os.path.isdir(fp):
            continue
        if a.only and fac not in a.only:
            continue
        for fn in sorted(os.listdir(fp)):
            if not fn.endswith(".json"):
                continue
            d = json.load(open(os.path.join(fp, fn), encoding="utf-8"))
            key = f"{fac}|{d.get('difficulty') or fn[:-5]}"
            for st in d.get("stages") or []:
                for sp in st.get("strategies") or []:
                    why = (sp.get("why") or "").strip()
                    if not why:
                        continue
                    plan = canon(sp.get("plan") or sp.get("text"))
                    slot = store.setdefault(key, {}).setdefault(str(st["stage"]), {})
                    if slot.get(plan) == why:
                        continue
                    slot[plan] = why
                    added += 1
    print(f"新增/更新 {added} 条 → {OUT}")
    if a.dry:
        print("dry-run：未写文件")
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("factors:", len(store), "| 文件", os.path.getsize(OUT), "B")
    return 0


if __name__ == "__main__":
    sys.exit(main())