# -*- coding: utf-8 -*-
"""校验并规范化 factors-final.json 里的 boss_type：
- 把 `·`/空格去掉，改成与本体 TypeCombination 一致的写法（如 光·飞行 → 光飞行）；
- 用 26 个属性名做分段，判定是否真实存在的双属性组合；
- 报告非法/可疑值（不改写，交人工）。
"""
import os, sys, json, collections

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, os.path.join(HERE, "..", "ontology").replace("/", "\\"))
import type_multiplier as tm  # noqa: E402

NAMES = sorted({v for v in tm.EID2NAME.values()}, key=len, reverse=True)
VALID = {frozenset(tm.EID2NAME[e] for e in els) for els in tm.TC2ELEMS.values()}


def segment(s):
    """把字符串切成属性名序列（优先长名），返回 None 表示有切不掉的残渣。"""
    out, i = [], 0
    while i < len(s):
        for n in NAMES:
            if s.startswith(n, i):
                out.append(n)
                i += len(n)
                break
        else:
            return None
    return out


def main():
    p = f"{HERE}/factors-final.json"
    d = json.load(open(p, encoding="utf-8"))
    changed = 0
    bad = collections.Counter()
    for e in d:
        for s in e["stages"]:
            bt = s.get("boss_type")
            if not isinstance(bt, str) or not bt:
                continue
            clean = bt.replace("·", "").replace(" ", "").strip()
            if clean != bt:
                s["boss_type"] = clean
                changed += 1
            seg = segment(clean)
            if seg is None:
                bad[clean] += 1
            elif frozenset(seg) not in VALID:
                bad[clean] += 1
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"规范化 boss_type 的关数 = {changed}")
    print(f"非法/不存在组合 = {sum(bad.values())} 关，涉及 {len(bad)} 种")
    for k, v in bad.most_common(30):
        print(f"  {k} × {v}")


if __name__ == "__main__":
    main()