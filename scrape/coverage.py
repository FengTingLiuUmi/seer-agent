# -*- coding: utf-8 -*-
"""交付前的覆盖度体检：打印每个难度档的字段完整率 + 缺口清单。
运行：PYTHONUTF8=1 python coverage.py
"""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")


def load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def main():
    fin = load(f"{HERE}/factors-final.json") or []
    why = load(f"{HERE}/factors-why.json") or []
    why_by = {}
    for w in why:
        if isinstance(w, dict):
            k = ((w.get("factor") or "").replace("·", "").replace(" ", ""), w.get("difficulty") or "地狱")
            why_by[k] = w.get("whys") or []

    def whys_of(factor, difficulty):
        return why_by.get((factor.replace("·", "").replace(" ", ""), difficulty), [])

    stages = [(e["factor"], s) for e in fin for s in e["stages"]]
    print(f"因子 = {len(fin)}，关卡 = {len(stages)}")
    print()

    by_d = collections.defaultdict(list)
    for f, s in stages:
        by_d[s["difficulty"]].append((f, s))

    hdr = f"{'难度':<6}{'关数':>6}{'特性':>8}{'属性':>8}{'血量':>8}{'攻略':>8}{'阵容':>8}{'why':>8}"
    print(hdr)
    print("-" * len(hdr.encode("gbk")[:0]) + "-" * 62)
    for d in ("地狱", "困难", "简单"):
        rows = by_d.get(d, [])
        if not rows:
            continue
        t = sum(1 for _, s in rows if s.get("traits"))
        b = sum(1 for _, s in rows if s.get("boss_type"))
        hp = sum(1 for _, s in rows if s.get("boss_hp"))
        st = sum(1 for _, s in rows if s.get("strategies"))
        pe = sum(1 for _, s in rows if s.get("pets"))
        wh = sum(1 for f, s in rows if any(x.get("stage") == s["stage"] for x in whys_of(f, d)))
        print(f"{d:<6}{len(rows):>6}{t:>8}{b:>8}{hp:>8}{st:>8}{pe:>8}{wh:>8}")

    print()
    print("--- 缺口 ---")
    no_any = [e["factor"] for e in fin if not any(s.get("traits") for s in e["stages"])]
    print(f"无任何特性 = {len(no_any)}: {no_any}")
    no_hard = [e["factor"] for e in fin if not any(s["difficulty"] == "地狱" for s in e["stages"])]
    print(f"无地狱档 = {len(no_hard)}: {no_hard}")
    no_why = [e["factor"] for e in fin
              if e["stages"] and not any(any(x.get("stage") == s["stage"]
                                             for x in whys_of(e["factor"], s["difficulty"]))
                                         for s in e["stages"])]
    print(f"无 why 解释 = {len(no_why)}")
    miss_type = [(f, s["difficulty"], s["stage"]) for f, s in stages if not s.get("boss_type")]
    print(f"缺 Boss 属性 = {len(miss_type)} 关" + (f"（示例 {miss_type[:5]}）" if miss_type else ""))
    miss_hp = [(f, s["difficulty"], s["stage"]) for f, s in stages if not s.get("boss_hp")]
    print(f"缺血量 = {len(miss_hp)} 关")


if __name__ == "__main__":
    main()