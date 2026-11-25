# -*- coding: utf-8 -*-
"""doc_why_patch.py —— 把 why 补丁应用到因子关 JSON，并自检「其它字段零改动」。

用法（workdir=workspace 根）：
    python seer-factor-kb/ontology/doc_why_patch.py <因子名> <难度> <patch.json> [--dry]

patch.json 形如：
    {"1|0": "why 文本", "1|1": "...", "4|0": "..."}
只允许改 stages[i].strategies[j].why 与（可选）stages[i].why（键写作 "1|stage"）。
应用前先把整份文档除这两类字段外做深比较，不一致就中止。
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def scrub(doc):
    d = copy.deepcopy(doc)
    for st in d.get("stages") or []:
        st.pop("why", None)
        for sp in st.get("strategies") or []:
            sp.pop("why", None)
    return d


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    factor, diff, patch_path = sys.argv[1], sys.argv[2], sys.argv[3]
    dry = "--dry" in sys.argv
    docp = os.path.join(ROOT, "kb", "docs", factor, diff + ".json")
    doc = json.load(open(docp, encoding="utf-8"))
    patch = json.load(open(patch_path, encoding="utf-8"))
    before = scrub(doc)

    applied, skipped = [], []
    for key, why in patch.items():
        try:
            a, b = key.split("|")
            si = int(a)
            st = next(x for x in doc["stages"] if int(x["stage"]) == si)
        except StopIteration:
            skipped.append((key, "no such stage"))
            continue
        except Exception as e:
            skipped.append((key, f"bad key ({e})"))
            continue
        if b == "stage":
            st["why"] = why
            applied.append((key, len(why)))
            continue
        j = int(b)
        if not (0 <= j < len(st.get("strategies") or [])):
            skipped.append((key, "no such strategy"))
            continue
        if not str(why).strip():
            skipped.append((key, "empty why"))
            continue
        st["strategies"][j]["why"] = why
        applied.append((key, len(why)))

    if scrub(doc) != before:
        print("ABORT: 除 why 以外的字段被改动了")
        return 4
    print(f"applied {len(applied)} : " + ", ".join(f"{k}({n}B)" for k, n in applied))
    if skipped:
        print("SKIPPED: " + ", ".join(f"{k}={r}" for k, r in skipped))
    if dry:
        print("dry-run：未写文件")
        return 0
    with open(docp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    json.load(open(docp, encoding="utf-8"))
    print("written & revalidated", docp)
    return 0


if __name__ == "__main__":
    sys.exit(main())