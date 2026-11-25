# -*- coding: utf-8 -*-
"""把 resolve_pets 报的「待补充令牌」对到 SeerAPI 全量精灵表（pets-index.json）。
分级：exact（去·空格后完全同名）/ sub（唯一包含）/ amb（多候选）/ fuzzy（相似度>=0.75）/ none。
只把 exact 与 sub 视为可用；amb/fuzzy 进人工复核清单。宁缺毋滥，不猜。
输出：pets-supplement2.json
"""
import json, re, difflib, os

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")


def norm(s):
    return re.sub(r"[·•\s\-_]", "", str(s))


def main():
    idx = json.load(open(f"{HERE}/pets-index.json", encoding="utf-8"))
    miss = json.load(open(f"{HERE}/pets-resolved-final.json", encoding="utf-8"))["missing"]

    by_norm = {}
    for p in idx:
        by_norm.setdefault(norm(p["name"]), []).append(p)
    by_id = {int(p["id"]): p for p in idx}
    none = []

    exact, sub, amb, fuzzy, none = {}, {}, {}, {}, []
    for t in miss:
        n = norm(t)
        if not n:
            none.append(t)
            continue
        if n in by_norm:
            cands = sorted(by_norm[n], key=lambda p: p["id"])
            exact[t] = cands  # 可能多个同名 id
            continue
        # 安全方向：令牌是精灵名的缩短形（token ⊂ name），如 乐普斯 → 天兔·乐普斯
        cands = [p for p in idx if len(n) >= 2 and n in norm(p["name"])]
        if len(cands) == 1:
            sub[t] = cands
            continue
        if len(cands) > 1:
            amb[t] = sorted(cands, key=lambda p: (len(norm(p["name"])) - len(n), -p["id"]))[:6]
            continue
        # 危险方向：精灵名被塞进更长令牌（name ⊂ token），如 乌瑞亚 → 瑞亚、冥王断空破 → 冥王·断空
        rev = [p for p in idx if len(norm(p["name"])) >= 2 and norm(p["name"]) in n]
        if rev:
            amb[t] = sorted(rev, key=lambda p: (abs(len(norm(p["name"])) - len(n)), -p["id"]))[:6]
            continue
        best = sorted(idx, key=lambda p: -difflib.SequenceMatcher(None, n, norm(p["name"])).ratio())[:3]
        if best and difflib.SequenceMatcher(None, n, norm(best[0]["name"])).ratio() >= 0.75:
            fuzzy[t] = [(p, round(difflib.SequenceMatcher(None, n, norm(p["name"])).ratio(), 2)) for p in best]
            continue
        none.append(t)

    # 同一 seerapiId 只保留一次（多个令牌指向同一只精英灵时合并为 variants）
    pets = {}

    def take(tok, pid):
        p = by_id[pid]
        e = pets.setdefault(str(p["id"]), {
            "name": p["name"], "seerapiId": str(p["id"]),
            "type": (p.get("type") or {}).get("name") or "", "variants": [],
        })
        if tok != p["name"] and tok not in e["variants"]:
            e["variants"].append(tok)

    for t, cands in list(exact.items()) + list(sub.items()):
        take(t, sorted(cands, key=lambda x: -x["id"])[0]["id"])

    # 人工判定覆盖（pets-token-override.json）
    ov = {"accept": {}, "reject": []}
    ovp = f"{HERE}/pets-token-override.json"
    if os.path.exists(ovp):
        ov = json.load(open(ovp, encoding="utf-8"))
    for t, pid in (ov.get("accept") or {}).items():
        if int(pid) in by_id:
            take(t, int(pid))
            amb.pop(t, None)
            fuzzy.pop(t, None)
            if t in none:
                none.remove(t)
    for t in ov.get("reject") or []:
        amb.pop(t, None)
        fuzzy.pop(t, None)
        if t not in none:
            none.append(t)

    out = {
        "pets": sorted(pets.values(), key=lambda x: x["name"]),
        "ambiguous": {k: [{"id": p["id"], "name": p["name"]} for p in v] for k, v in amb.items()},
        "fuzzy": {k: [{"id": p["id"], "name": p["name"], "ratio": r} for p, r in v] for k, v in fuzzy.items()},
        "noise_or_unresolved": sorted(none),
    }
    json.dump(out, open(f"{HERE}/pets-supplement2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"待补充令牌 {len(miss)}")
    print(f"  确定为精灵 = {len(out['pets'])} 只（来自 exact/sub）")
    print(f"  多候选待复核 = {len(out['ambiguous'])}")
    print(f"  模糊待复核   = {len(out['fuzzy'])}")
    print(f"  非精灵/未解析 = {len(out['noise_or_unresolved'])}")
    # 类型缺失统计（type 可能是空串）
    notype = [p["name"] for p in out["pets"] if not p["type"]]
    print(f"  其中 type 为空 = {len(notype)}: {notype[:10]}")


if __name__ == "__main__":
    main()