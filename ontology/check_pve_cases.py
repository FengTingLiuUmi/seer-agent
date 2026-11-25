# -*- coding: utf-8 -*-
"""check_pve_cases.py —— 跑 PVE 回归验证集（pve_cases.json）。

用途：把用户在会话里指出过的具体问题固化成断言。改本体 / 改文档 why / 改别名后跑一遍，
全绿才算没回退。规则清单见 pve_cases.json 的 _rules（不可执行，仅供阅读）。

用法（workdir=workspace 根）：
    python seer-factor-kb/ontology/check_pve_cases.py
    python seer-factor-kb/ontology/check_pve_cases.py --only nick 技能...   # 只跑某类
    python seer-factor-kb/ontology/check_pve_cases.py -v                   # 打印明细

退出码：0 全通过；1 有失败。
"""
import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CASES = os.path.join(HERE, "pve_cases.json")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, ".pylibs"))

from rdflib import Graph, Namespace, RDF, RDFS  # noqa: E402

SEER = Namespace("http://example.org/seer#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

_G = None


def graph():
    global _G
    if _G is None:
        g = Graph()
        g.parse(os.path.join(HERE, "seer-all.owl"), format="xml")
        _G = g
    return _G


def load_kb():
    import seer_kb_mcp as kb
    return kb


def check_nick(c, kb):
    r = kb.tool_nick(c["query"])
    got = [m["id"] for m in r.get("matches") or []]
    want = list(c["expect_ids"])
    ok = set(got) == set(want)
    return ok, f"期望 {want} 实际 {got}"


def check_skill(c, kb):
    r = kb.tool_skill(name=c["query"])
    if r.get("miss"):
        return False, "本体查不到该技能"
    hits = r.get("skills") or r.get("matches") or []
    if isinstance(hits, dict):
        hits = [hits]
    if not hits:
        return False, f"无命中：{r}"
    s = hits[0]
    bad = []
    for k, v in (c.get("expect") or {}).items():
        if s.get(k) != v:
            bad.append(f"{k} 期望 {v} 实际 {s.get(k)}")
    for k in c.get("forbid_keys") or []:
        if k in s:
            bad.append(f"出现了不该有的字段 {k}={s.get(k)}")
    effs = " ".join(str(e.get("info") or "") for e in (s.get("效果") or []))
    for frag in c.get("effect_contains") or []:
        if frag not in effs:
            bad.append(f"效果里缺「{frag}」")
    return (not bad), ("; ".join(bad) if bad else "OK")


def check_lineup(c, kb):
    r = kb.tool_nick(c["query"])
    ls = r.get("lineups") or []
    if not ls:
        return False, "nick 没返回阵容"
    got = sorted(sum((x["member_ids"] for x in ls), []))
    want = sorted(c["expect_member_ids"])
    return (got == want), f"成员期望 {want} 实际 {got}"


def check_pet(c, kb):
    r = kb.tool_nick(c["query"])
    if not r.get("matches"):
        return False, f"查不到 {c['query']}"
    p = r["matches"][0]
    bad = []
    for k, v in (c.get("expect") or {}).items():
        if p.get(k) != v:
            bad.append(f"{k} 期望 {v} 实际 {p.get(k)}")
    roles = " ".join(p.get("roles") or [])
    for frag in c.get("roles_contains") or []:
        if frag not in roles:
            bad.append(f"roles 里缺「{frag}」（实际 {p.get('roles')}）")
    for frag in c.get("roles_forbid") or []:
        if frag in roles:
            bad.append(f"roles 里不该有「{frag}」（实际 {p.get('roles')}）")
    note = p.get("站场用法") or ""
    for frag in c.get("sustain_note_must") or []:
        if frag not in note:
            bad.append(f"站场用法里缺「{frag}」")
    for frag in c.get("sustain_note_forbid") or []:
        if frag in note:
            bad.append(f"站场用法里不该出现「{frag}」")
    return (not bad), ("; ".join(bad) if bad else "OK")


def check_shared_skill(c):
    """凡是会某个技能的精灵，站场技都必须指回该技能。
    对应「同样拥有奇镰解放的也是」：不能只给希可洛标，卡莎/小镰 漏标就是缺口。"""
    g = graph()
    sk = None
    for s in g.subjects(RDF.type, SEER.Skill):
        if str(g.value(s, RDFS.label) or "") == c["skill_name"]:
            sk = s
            break
    if sk is None:
        return False, f"本体没有技能「{c['skill_name']}」"
    owners = [p for p in g.subjects(SEER.hasSkill, sk)]
    if not owners:
        return False, "没有精灵挂这个技能"
    bad = []
    for p in owners:
        ss = g.value(p, SEER.sustainSkill)
        if ss != sk:
            bad.append(f"{g.value(p, RDFS.label) or p} 未标站场技")
    return (not bad), ("; ".join(bad) if bad else f"{len(owners)} 只全会都指向该技能")


def check_soulmark(c, kb):
    r = kb.tool_soulmark(name=c["pet"])
    if not r.get("matches"):
        return False, f"查不到 {c['pet']} 的魂印"
    want = str(c.get("sid"))
    sm = None
    for m in r["matches"]:
        for x in m.get("soulmark") or []:
            if str(x.get("id")) == want:
                sm = x
                break
        if sm:
            break
    if sm is None:
        return False, f"该精灵的魂印里没有 {want}"
    bad = []
    for k, v in (c.get("expect") or {}).items():
        if sm.get(k) != v:
            bad.append(f"{k} 期望 {v} 实际 {sm.get(k)}")
    for k, v in (c.get("expect_extra") or {}).items():
        if sm.get(k) != v:
            bad.append(f"{k} 期望 {v} 实际 {sm.get(k)}")
    rem = sm.get("备注") or ""
    for frag in c.get("remark_contains") or []:
        if frag not in rem:
            bad.append(f"备注里缺「{frag}」")
    return (not bad), ("; ".join(bad) if bad else "OK")


def _doc(c):
    p = os.path.join(ROOT, "kb", "docs", c["doc"], f"{c.get('difficulty', '地狱')}.json")
    return json.load(open(p, encoding="utf-8"))


def check_doc_why(c):
    d = _doc(c)
    st = next((x for x in d["stages"] if int(x["stage"]) == int(c["stage"])), None)
    if st is None:
        return False, "没有这一关"
    sp = st["strategies"][int(c.get("index", 0))]
    why = sp.get("why") or ""
    bad = []
    for frag in c.get("must_contain") or []:
        if frag not in why:
            bad.append(f"why 缺「{frag}」")
    for frag in c.get("must_not_contain") or []:
        if frag in why:
            bad.append(f"why 不该含「{frag}」")
    return (not bad), ("; ".join(bad) if bad else "OK")


def check_doc_all_why(c):
    d = _doc(c)
    empt = []
    badwords = []
    for st in d["stages"]:
        for j, sp in enumerate(st.get("strategies") or []):
            w = (sp.get("why") or "").strip()
            if not w:
                empt.append(f"st{st['stage']}[{j}]")
            for b in ("未核实", "未收录"):
                if b in w:
                    badwords.append(f"st{st['stage']}[{j}]含{b}")
    msgs = []
    if empt:
        msgs.append("空 why: " + ", ".join(empt))
    if badwords:
        msgs.append("噪音词: " + ", ".join(badwords))
    return (not msgs), ("; ".join(msgs) if msgs else "OK")


def check_absent(c):
    if c["what"] == "property":
        iri = c["iri"]
        from rdflib import URIRef
        g = graph()
        found = (URIRef(iri), None, None) in g or any(True for _ in g.predicate_objects(URIRef(iri)))
        return (not found), ("属性仍存在" if found else "OK")
    if c["what"] == "file":
        p = os.path.join(ROOT, "..", c["path"])
        p = os.path.abspath(p)
        found = os.path.exists(p)
        return (not found), (f"文件仍存在：{p}" if found else "OK")
    return False, f"未知 what={c['what']}"


def check_coverage(c):
    g = graph()
    idx = {}
    for pred in (SKOS.altLabel, RDFS.label):
        for p in g.subjects(RDF.type, SEER.Pet):
            for lb in g.objects(p, pred):
                idx.setdefault(str(lb).strip(), p)
    docs = os.path.join(ROOT, "docs")
    used = {}
    for fac in sorted(os.listdir(docs)):
        fp = os.path.join(docs, fac)
        if not os.path.isdir(fp):
            continue
        for fn in sorted(os.listdir(fp)):
            if not fn.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(fp, fn), encoding="utf-8"))
            except Exception:       # noqa: BLE001
                continue
            for st in d.get("stages") or []:
                for sp in st.get("strategies") or []:
                    for pn in sp.get("pets") or []:
                        used.setdefault(pn, None)
    zero = []
    for pn in used:
        p = idx.get(pn)
        if p is None:
            continue
        if not list(g.objects(p, SEER.hasSkill)):
            zero.append(pn)
    # 技能清单不全：用 onto_fill 缓存里的 API 条数比对
    cachep = os.path.join(HERE, "skill-cache.json")
    partial = []
    if os.path.exists(cachep):
        cache = json.load(open(cachep, encoding="utf-8"))
        for pn in used:
            p = idx.get(pn)
            if p is None:
                continue
            pid = str(p).split("#")[-1].split("_")[-1]
            api = cache.get(f"https://api.seerapi.com/v1/pet/{pid}")
            if not api:
                continue
            want = len(api.get("skill") or [])
            have = len(list(g.objects(p, SEER.hasSkill)))
            if want and have < want:
                partial.append(f"{pn}({have}/{want})")
    msgs = []
    if len(zero) > int(c.get("expect_zero_skill", 0)):
        msgs.append(f"0 技能 {len(zero)} 只: {', '.join(zero[:6])}")
    if len(partial) > int(c.get("expect_incomplete_skill", 0)):
        msgs.append(f"技能不全 {len(partial)} 只: {', '.join(partial[:6])}")
    return (not msgs), ("; ".join(msgs) if msgs else "OK")


KINDS = {
    "nick": check_nick,
    "pet": check_pet,
    "lineup": check_lineup,
    "skill": check_skill,
    "soulmark": check_soulmark,
    "doc_why": check_doc_why,
    "doc_all_why": check_doc_all_why,
    "shared_skill": check_shared_skill,
    "absent": check_absent,
    "coverage": check_coverage,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="只跑这些 kind")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(CASES, encoding="utf-8"))
    kb = load_kb()
    rows, fails = [], 0
    for c in cfg["cases"]:
        if a.only and c["kind"] not in a.only:
            continue
        fn = KINDS.get(c["kind"])
        if fn is None:
            rows.append((c["id"], "SKIP", f"未知 kind={c['kind']}"))
            continue
        try:
            if c["kind"] in ("nick", "pet", "lineup", "skill", "soulmark"):
                ok, msg = fn(c, kb)
            else:
                ok, msg = fn(c)
        except Exception as e:          # noqa: BLE001
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += (not ok)
        rows.append((c["id"], "PASS" if ok else "FAIL", msg))
    w = max(len(r[0]) for r in rows) if rows else 10
    for cid, st, msg in rows:
        if st == "PASS" and not a.verbose:
            print(f"{cid:{w}}  {st}")
        else:
            print(f"{cid:{w}}  {st}  {msg}")
    print(f"\n{len(rows) - fails}/{len(rows)} 通过" + ("（全部通过）" if not fails else f"，{fails} 条失败"))
    pend = cfg.get("_pending") or []
    if pend:
        print("\n未完成（已知缺口，不计入判定）：")
        for i, p in enumerate(pend, 1):
            print(f"  {i}. {p}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())