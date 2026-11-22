# -*- coding: utf-8 -*-
"""根据 factors-final.json (+ 可选 factors-why.json) 渲染可审核交付文档 markdown。
运行：PYTHONUTF8=1 python render_deliverable.py [--out 交付文档.md]
"""
import os, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

def load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def render_pet_appendix():
    """附录：精灵补充与消歧（供审核「本体补了什么、哪些没敢补」）。"""
    s1 = load(f"{HERE}/pets-supplement.json") or {}
    s2 = load(f"{HERE}/pets-supplement2.json") or {}
    ov = load(f"{HERE}/pets-token-override.json") or {}
    sup = (s1.get("pets") or []) + (s2.get("pets") or [])
    resolved = load(f"{HERE}/pets-resolved-final.json") or {}
    stats = load(f"{HERE}/../ontology/supp-stats.json") or {}
    known = resolved.get("known") or {}
    missing = resolved.get("missing") or []

    L = ["", "---", "", "## 附录 · 精灵补充与消歧", ""]
    L.append(f"- 攻略里出现的精灵令牌（去重）：**{len(known) + len(missing)}**")
    L.append(f"- 已对回本体：**{len(known)}**")
    L.append(f"- 仍未解析（昵称/组合/技能名，未猜）：**{len(missing)}**")
    L.append(f"- 补充表收录精灵：**{stats.get('supp_pets', len(sup))}** 只（含 seerapiId / 属性 / 别名，内含 21 组错写字修正）")
    L.append(f"- 本体精灵总数：**{stats.get('onto_pets', '?')}** 只")
    L.append("")
    L.append("### 错写字 → 正式名（人工核对）")
    L.append("")
    L.append("| 攻略写法 | 正式名 | id | 依据 |")
    L.append("|---|---|---|---|")
    reasons = ov.get("_reasons") or {}
    by_id = {}
    for p in sup:
        by_id[str(p.get("seerapiId"))] = p
    for tok, pid in sorted((ov.get("accept") or {}).items()):
        p = by_id.get(str(pid)) or {}
        L.append(f"| {tok} | {p.get('name', '?')} | {pid} | {reasons.get(tok, '')} |")
    rej = ov.get("reject") or []
    if rej:
        L.append("")
        L.append("### 未收（无法确证，宁缺毋滥）")
        L.append("")
        for t in rej:
            L.append(f"- `{t}` — {reasons.get(t, '')}")
    L.append("")
    L.append("### 仍未解析的令牌")
    L.append("")
    L.append("、".join(f"`{m}`" for m in missing))
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=f"{HERE}/../赛尔号因子PVE交付文档.md")
    args = ap.parse_args()

    fin = load(f"{HERE}/factors-final.json") or []
    why = load(f"{HERE}/factors-why.json") or []
    why_map = {}
    for w in why:
        if isinstance(w, dict):
            key = ((w.get("factor") or "").replace("·", "").replace(" ", ""),
                   w.get("difficulty") or "地狱")
            why_map[key] = w.get("whys") or []

    def whys_of(factor, difficulty):
        return why_map.get((factor.replace("·", "").replace(" ", ""), difficulty), [])

    diff_order = {"地狱": 0, "困难": 1, "简单": 2}

    n = len(fin)
    with_traits = sum(1 for e in fin if any("traits" in s for s in e["stages"]))
    with_why = sum(1 for e in fin
                   if any(any(x.get("stage") == s["stage"] for x in whys_of(e["factor"], s["difficulty"]))
                          for s in e["stages"]))

    L = []
    L.append("# 赛尔号 · 因子关 PVE 知识抽取（交付稿）\n")
    L.append("> 待人工审核。宁缺毋滥：缺的字段一律省略，不编造。")
    L.append("")
    L.append("## 概览")
    L.append("")
    L.append(f"- 因子（去重）总数：**{n}**")
    L.append(f"- 含逐关 Boss 特性的因子：**{with_traits}/{n}**")
    L.append(f"- 含「为什么这样打」解释的因子：**{with_why}/{n}**")
    L.append("- 数据来源：雷小伊论坛『因子脚本分享』969 帖清单（实际抓取正文 368 帖）+ B站/镜像 234 个地狱因子 + SeerAPI 补精灵。")
    L.append("")

    # 逐档字段完整率（审核用体检表）
    stages_all = [(e["factor"], s) for e in fin for s in e["stages"]]
    by_d = {}
    for f, s in stages_all:
        by_d.setdefault(s["difficulty"], []).append((f, s))
    L.append("### 字段完整率")
    L.append("")
    L.append("| 难度 | 关数 | 特性 | Boss属性 | 血量 | 攻略 | 阵容 | 为什么这样打 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for d in ("地狱", "困难", "简单"):
        rows = by_d.get(d, [])
        if not rows:
            continue

        def cnt(k):
            return sum(1 for _, s in rows if s.get(k))

        def whyn():
            n = 0
            for f, s in rows:
                if any(x.get("stage") == s["stage"] for x in whys_of(f, d)):
                    n += 1
            return n

        L.append(f"| {d} | {len(rows)} | {cnt('traits')} | {cnt('boss_type')} | {cnt('boss_hp')} | "
                 f"{cnt('strategies')} | {cnt('pets')} | {whyn()} |")
    L.append("")
    L.append(f"> 合计 {len(fin)} 因子 / {len(stages_all)} 关。**缺 Boss 属性 "
             f"{sum(1 for _, s in stages_all if not s.get('boss_type'))} 关、缺血量 "
             f"{sum(1 for _, s in stages_all if not s.get('boss_hp'))} 关**——"
             "集中在困难档（论坛帖只写打法不标属性）与部分地狱关（B站原文未标）；"
             "Boss 形态不定，属性无法从因子名推出，故不推断。")
    L.append("")
    L.append("## 逐因子")
    L.append("")

    # 按 地狱优先 排序
    def sortkey(e):
        ds = [s.get("difficulty") for s in e["stages"]]
        d = min((diff_order.get(x, 9) for x in ds), default=9)
        return (d, e["factor"])

    for e in sorted(fin, key=sortkey):
        name = e["factor"]
        stages = sorted(e["stages"], key=lambda s: (diff_order.get(s["difficulty"], 9), s["stage"]))
        # 按难度分组
        bydiff = {}
        for s in stages:
            bydiff.setdefault(s["difficulty"], []).append(s)
        L.append(f"### {name}")
        if e.get("ban"):
            L.append(f"- **Ban（禁用）**：{'、'.join(e['ban'])}")
        if e.get("tids"):
            L.append(f"- 来源帖：{', '.join('thread-%s' % t for t in e['tids'])}")
        for d in ("地狱", "困难", "简单"):
            for s in bydiff.get(d, []):
                L.append(f"**[{d}] 第{s['stage']}关**")
                if s.get("boss_type"):
                    L.append(f"- Boss 属性：`{s['boss_type']}`")
                if s.get("boss_hp"):
                    L.append(f"- 血量：`{s['boss_hp']}`")
                if s.get("traits"):
                    L.append(f"- 特性：{s['traits']}")
                if s.get("strategies"):
                    L.append(f"- 攻略：{' ；'.join(s['strategies'])}")
                if s.get("pets"):
                    L.append(f"- 阵容：{'、'.join(s['pets'])}")
                wk = whys_of(name, d)
                w = next((x for x in wk if x.get("stage") == s["stage"]), None)
                if w and w.get("why"):
                    L.append(f"- 为什么这样打：{w['why']}")
        L.append("")

    text = "\n".join(L) + render_pet_appendix()
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"渲染 {n} 因子 -> {args.out}（{len(text)} 字符）")


if __name__ == "__main__":
    main()