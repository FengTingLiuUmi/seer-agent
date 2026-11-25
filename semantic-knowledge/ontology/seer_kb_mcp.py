# -*- coding: utf-8 -*-
"""seer_kb_mcp.py —— 赛尔号 PVE 本体查询的本地 MCP stdio 服务（无第三方依赖，仅 rdflib）。
对外暴露 5 个工具：nick / boss / role / mult / ban。
协议：MCP stdio（换行分隔的 JSON-RPC 2.0）。stdout 只发协议消息，日志走 stderr。
"""
import os, sys, json
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, HERE)  # 便于 import type_multiplier
sys.path.insert(0, os.path.join(HERE, "..", "kb").replace("\\", "/"))  # 便于 import plan/mechanisms

from rdflib import Graph, RDF, RDFS, Namespace, SKOS, Literal, URIRef
import glob, re  # 异常状态模块（status 工具）用

SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")

_G = None
_G_MTIME = None


def graph():
    """按 mtime 自动重载：本体重建后无需重启 MCP 进程。"""
    global _G, _G_MTIME
    path = os.path.join(HERE, "seer-all.owl")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        mt = None
    if _G is None or mt != _G_MTIME:
        g = Graph()
        g.parse(path, format="xml")
        _G, _G_MTIME = g, mt
    return _G


def ln(u):
    return str(u).rsplit("#", 1)[-1]


def label(node):
    """确定性取名：同一实体可能有多个 rdfs:label（58 只精灵存在「纯名」和「纯名（PVE 注解）」两条），
    graph().objects() 的先后是不确定的，直接 return 第一条会时对时错——曾把「咤克斯」解析成基础形态。
    规则：优先不带括号注解的，其次最短的，最后按字典序兜底。"""
    labs = [str(o) for o in graph().objects(node, RDFS.label)]
    if not labs:
        return ln(node)
    import re as _re

    def rank(s):
        annotated = 1 if ("（" in s or "(" in s) else 0
        return (annotated, len(s), s)

    return sorted(labs, key=rank)[0]


def pyval(o):
    if isinstance(o, Literal):
        v = o.toPython()
    else:
        v = str(o)
    if isinstance(v, Decimal):
        return float(v)
    return v


def id_of(node):
    v = graph().value(node, SEER.seerapiId)
    return str(v) if v is not None else None


def type_name(tc):
    els = [label(e) for e in graph().objects(tc, SEER.combinationOf)]
    return "/".join(els) if els else label(tc)


def pet_brief(pet):
    rows = [label(r) for r in graph().objects(pet, PVE.hasRole)]
    tcs = [type_name(t) for t in graph().objects(pet, SEER.hasTypeCombination)]
    note = graph().value(pet, RDFS.comment)
    out = {
        "id": id_of(pet),
        "label": label(pet),
        "type": tcs,
        "roles": rows,
        "note": str(note) if note else "",
    }
    # 站场技：这只精灵靠哪个技能站住（比"会哪些技能"更接近"该怎么用"）
    ss = graph().value(pet, SEER.sustainSkill)
    if ss is not None:
        out["站场技"] = label(ss)
        out["站场技id"] = id_of(ss)
        sn = graph().value(pet, SEER.sustainNote)
        if sn:
            out["站场用法"] = str(sn)
    return out


# =============== 异常状态（seer-status.ttl 模块） ===============
# 只读辅助：不改变任何既有工具的返回结构。ontology 里没有 seer:StatusAilment 个
# 体时（即尚未合并 seer-status.ttl），所有函数退化为空结果，既有 7 个工具行为不变。

CATEGORY_IRI = {
    "控制": SEER.ControlStatus, "控场": SEER.ControlStatus, "control": SEER.ControlStatus,
    "持续伤害": SEER.DamageOverTimeStatus, "持续": SEER.DamageOverTimeStatus,
    "dot": SEER.DamageOverTimeStatus,
    "削弱": SEER.WeakenStatus, "weak": SEER.WeakenStatus, "weaken": SEER.WeakenStatus,
    "附属": SEER.AuxiliaryStatus, "aux": SEER.AuxiliaryStatus,
    "限制": SEER.RestrictStatus, "restrict": SEER.RestrictStatus,
}

STATUS_DOCS = os.path.join(HERE, "..", "kb", "docs").replace("\\", "/")


def status_inds(cat_iri=None):
    """所有异常状态个体（可按类别类过滤）。"""
    g = graph()
    out = []
    for s in set(g.subjects(RDF.type, SEER.StatusAilment)):
        if cat_iri is not None and (s, RDF.type, cat_iri) not in g:
            continue
        out.append(s)
    out.sort(key=lambda x: (label(x), ln(x)))
    return out


def _b(g, s, pred):
    """单个字面量 → python 值；无则 None。"""
    v = g.value(s, pred)
    return pyval(v) if v is not None else None


def _strs(g, s, pred):
    return [str(o) for o in g.objects(s, pred)]


def status_brief(s):
    g = graph()
    cats = []
    for o in g.objects(s, SEER.statusCategory):
        c = str(o)
        if c not in cats:
            cats.append(c)
    return {
        "name": str(g.value(s, SEER.statusName) or label(s)),
        "category": cats,
        "isControl": _b(g, s, SEER.isControl),
        "bossStageCount": _b(g, s, SEER.bossStageCount),
        "pveRelevant": _b(g, s, SEER.pveRelevant),
        "seerapiId": _b(g, s, SEER.seerapiId),
        "iri": str(s),
    }


def _status_keys(s):
    """状态名 + 全部俗称（用于文本/查询匹配）。"""
    g = graph()
    keys = [str(g.value(s, SEER.statusName) or label(s))]
    for o in g.objects(s, SEER.statusAlias):
        k = str(o)
        if k and k not in keys:
            keys.append(k)
    return keys


def _boss_stages(s):
    """状态 → 会施加它的 Boss 关卡（因子/难度/关号/敌人）。"""
    g = graph()
    rows = []
    for en in g.objects(s, SEER.inflictedByEnemy):
        st = next(iter(g.subjects(PVE.hasEnemy, en)), None)
        fac = next(iter(g.subjects(SEER.hasStage, st)), None) if st is not None else None
        d = g.value(st, PVE.difficulty) if st is not None else None
        n = pyval(g.value(st, PVE.stageNumber)) if st is not None else None
        rows.append({"factor": label(fac) if fac is not None else label(en),
                     "difficulty": label(d) if d is not None else "",
                     "stage": n,
                     "enemy": label(en)})
    rows.sort(key=lambda r: (r["factor"], r["difficulty"], r["stage"] or 0))
    return rows


def status_detail(s):
    """一个状态的完整字段（缺失的字段直接不出现；stackable 单独给 None 表示 unknown）。"""
    g = graph()
    d = status_brief(s)
    for key, pred in [("alias", SEER.statusAlias), ("effect", SEER.effect),
                      ("duration", SEER.duration), ("applyCondition", SEER.applyCondition),
                      ("cureMethod", SEER.cureMethod), ("immuneRule", SEER.immuneRule),
                      ("officialCategory", SEER.officialCategory),
                      ("counterAdvice", SEER.counterAdvice),
                      ("appliedBySkill", SEER.appliedBySkill),
                      ("sources", SEER.dataSource)]:
        vals = _strs(g, s, pred)
        if vals:
            d[key] = vals if len(vals) > 1 else vals[0]
    st = g.value(s, SEER.stackable)
    d["stackable"] = bool(st.toPython()) if st is not None else None
    if d["stackable"] is None:
        d["stackableNote"] = "unknown：SeerAPI 无此字段，本体不做推断"
    pets = [{"id": id_of(p), "label": label(p)} for p in g.objects(s, SEER.inflictedByPet)]
    if pets:
        pets.sort(key=lambda x: (x["label"], str(x["id"])))
        d["appliedByPet"] = pets
    bs = _boss_stages(s)
    if bs:
        d["bossStages"] = bs
    return d


def status_detail_from_text(text):
    """Boss 机制文本 → 命中的异常状态明细（用于 boss 工具的 statusDetail）。"""
    if not text:
        return []
    out = []
    prob = re.compile(r"(\d{1,3}\s*%|100%|高概率|大概率|概率)")
    lvl = re.compile(r"(高级|低级)")
    for s in status_inds():
        keys = [k for k in _status_keys(s) if len(k) >= 1]
        hit = [k for k in keys if k in text]
        if not hit:
            continue
        segs = []
        for seg in re.split(r"[;；]", text):
            seg = seg.strip()
            if seg and any(k in seg for k in keys):
                segs.append(seg)
        joined = "；".join(segs) if segs else text
        b = status_brief(s)
        item = {"status": b["name"], "category": b["category"], "isControl": b["isControl"],
                "effect": str(graph().value(s, SEER.effect) or "")}
        cm = graph().value(s, SEER.cureMethod)
        if cm:
            item["cureMethod"] = str(cm)
        ir = graph().value(s, SEER.immuneRule)
        if ir:
            item["immuneRule"] = str(ir)
        item["matched"] = segs[:3]
        m = prob.search(joined)
        if m:
            item["chance"] = m.group(1).replace(" ", "")
        m2 = lvl.search(joined)
        if m2:
            item["level"] = m2.group(1)
        item["iri"] = b["iri"]
        out.append(item)
    out.sort(key=lambda x: (not x["isControl"], x["status"]))
    return out


def _control_by_status():
    """docs 现算 control 项的状态细分：{状态名: {n, n_control}} + 说明。不写 kb/stats.json。"""
    g = graph()
    names = []
    for s in status_inds():
        n = str(g.value(s, SEER.statusName) or label(s))
        if n not in [x for x in names]:
            names.append(n)
    if not names:
        return {}, None
    n = {k: 0 for k in names}
    nc = {k: 0 for k in names}
    total = ctrl_total = unnamed = 0
    for fp in glob.glob(os.path.join(STATUS_DOCS, "*", "*.json")):
        if fp.endswith("catalog.json"):
            continue
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        for st in d.get("stages", []):
            tr = st.get("traits") or ""
            if not tr:
                continue
            total += 1
            isctrl = "control" in (st.get("mech") or [])
            if isctrl:
                ctrl_total += 1
            hit = False
            for k in names:
                if k in tr:
                    hit = True
                    n[k] += 1
                    if isctrl:
                        nc[k] += 1
            if isctrl and not hit:
                unnamed += 1
    out = {}
    for k in sorted(names, key=lambda x: (-n[x], x)):
        if n[k] > 0 or nc[k] > 0:
            out[k] = {"n": n[k], "n_control": nc[k]}
    if unnamed:
        out["未具名控场"] = {"n": unnamed, "n_control": unnamed}
    note = ("n=全库 %d 关中 traits 文本命中该状态名的关数；n_control=其中 mech 含 control 的关数"
            "（全库 control 关 %d）；同一关可命中多个状态，故各值不可加总、也不等于 %d；"
            "只列 n>0 的状态，其余状态未在 Boss 文本中出现。" % (total, ctrl_total, ctrl_total))
    return out, note


def tool_status(name=None, category=None):
    g = graph()
    if not status_inds():
        return {"error": "本体未含异常状态模块（seer:StatusAilment 无个体）：需先把 seer-status.ttl / "
                         "seer-status-abox.ttl 合并进 seer-all.owl"}
    cat_iri = None
    if category:
        cat_iri = CATEGORY_IRI.get(str(category).strip())
        if cat_iri is None:
            return {"error": f"未知类目：{category}（用 控制/持续伤害/削弱/附属/限制，或 control/dot/weaken/aux/restrict）"}
    cand = status_inds(cat_iri)
    if not name:
        return {"count": len(cand),
                "statuses": [status_brief(s) for s in cand],
                "hint": "传 name（状态名/俗称/技能名/精灵名）可拿完整字段；传 category 只按类目过滤。"}
    nm = str(name).strip()

    def match(kind, nodes):
        return [{"kind": kind, "detail": status_detail(s)} for s in nodes]

    exact = [s for s in cand if nm in _status_keys(s) or nm == ln(s)]
    if exact:
        return {"query": nm, "matches": match("status", exact)}
    sub = [s for s in cand if any(nm in k for k in _status_keys(s))]
    if sub:
        return {"query": nm, "matches": match("status", sub)}
    sk = [s for s in cand if any(nm in str(o) for o in g.objects(s, SEER.appliedBySkill))]
    if sk:
        return {"query": nm, "matches": match("skill", sk),
                "note": "按施加技能名匹配（appliedBySkill）"}
    pets = set()
    for p in g.subjects(RDF.type, SEER.Pet):
        if nm in label(p) or nm == id_of(p) or (p, SKOS.altLabel, Literal(nm)) in g:
            pets.add(p)
    if pets:
        hit = [s for s in cand if set(g.objects(s, SEER.inflictedByPet)) & pets]
        if hit:
            return {"query": nm, "matches": match("pet", hit),
                    "note": "按施加者精灵（Boss 物种）匹配"}
    return {"query": nm, "matches": [],
            "hint": "未命中状态名/俗称/技能名/精灵名。可先用 nick 消歧精灵名，或直接传 category 列出类目。"}


# ---------------- 魂印 / 战斗效果（seer-effects-abox.ttl） ----------------

_TAG_CACHE = None


def _txt(node, prop=SEER.desc):
    v = graph().value(node, prop)
    return str(v) if v is not None else None


def _tags_of(s):
    g = graph()
    return [label(t) for t in g.objects(s, SEER.soulmarkTag)]


def _pets_of(s):
    g = graph()
    return [label(p) for p in g.objects(s, SEER.affectsPet)]


def _has_effects():
    g = graph()
    for cls in ("Soulmark", "Buff", "BattleEffect", "FieldEffect", "PetEffect", "Item", "Mintmark"):
        if any(g.subjects(RDF.type, SEER[cls])):
            return True
    return False


def _soulmark_brief(s):
    g = graph()
    d = {"id": id_of(s), "desc": _txt(s), "tags": _tags_of(s), "pets": _pets_of(s),
         "pveEffective": pyval(g.value(s, SEER.pveEffective)) if g.value(s, SEER.pveEffective) is not None else None,
         "isAdv": pyval(g.value(s, SEER.isAdv)) if g.value(s, SEER.isAdv) is not None else None,
         "alias": _txt(s, SEER.effectAlias)}
    # 人工判定优先于 API 布尔（冲突示例：魂印 135 原文无标记、API=false、用户实测有效）
    verdict = _txt(s, SEER.pveVerdict)
    if verdict:
        d["PVE判定"] = verdict
    an = _txt(s, SEER.analyzeDesc)
    if an:
        d["analyzeDesc"] = an
    # 人工复核备注（rdfs:comment）。用于写清「为什么」——例如整条为什么 PVE 无效。
    cm = graph().value(s, RDFS.comment)
    if cm:
        d["备注"] = str(cm)
    return {k: v for k, v in d.items() if v not in (None, [], "")}


def tool_soulmark(name=None, tag=None, pve_only=False, limit=8):
    """魂印查询：精灵名/ID → 它的魂印；tag（吸血/减伤/…）→ 该标签下的魂印；不给参数 → 标签总览。"""
    g = graph()
    if not any(g.subjects(RDF.type, SEER.Soulmark)):
        return {"error": "本体未含魂印个体：需先跑 ingest_effects.py 并重跑 sync.py --merge-only"}
    try:
        limit = max(1, min(int(limit), 40))
    except Exception:
        limit = 8

    allsm = list(g.subjects(RDF.type, SEER.Soulmark))
    out = {"query": {"name": name, "tag": tag, "pve_only": bool(pve_only)}, "count": len(allsm)}

    def filt(nodes):
        if not pve_only:
            return nodes
        keep = []
        for s in nodes:
            v = g.value(s, SEER.pveEffective)
            if v is None or pyval(v) is True:
                keep.append(s)
        return keep

    if not name and not tag:
        cnt = {}
        for s in allsm:
            for t in _tags_of(s):
                cnt[t] = cnt.get(t, 0) + 1
        out["tags"] = sorted(({"tag": k, "count": v} for k, v in cnt.items()), key=lambda x: -x["count"])
        out["hint"] = "传 name（精灵名/ID）拿该精灵的魂印全文；传 tag 列该标签下的魂印；pve_only=true 只看 PVE 生效项"
        return out

    hits, note = [], None
    if name:
        nm = str(name).strip()
        pets = []
        for p in g.subjects(RDF.type, SEER.Pet):
            if nm == id_of(p) or nm == label(p):
                pets.append(p)
        if not pets:  # 退一步：子串（如只记得半截名字）
            pets = [p for p in g.subjects(RDF.type, SEER.Pet) if nm and nm in label(p)]
            if pets:
                note = "按精灵名子串匹配"
        if pets:
            for p in pets[:limit]:
                sms = filt(list(g.subjects(SEER.affectsPet, p)))
                hits.append({"pet": {"id": id_of(p), "label": label(p)},
                             "soulmark": [_soulmark_brief(s) for s in sms] or None})
        else:
            # 名字不是精灵：当关键词搜魂印描述
            kw = [s for s in allsm if nm and nm in (_txt(s) or "")]
            note = note or "没匹配到精灵名，按关键词搜魂印效果文本（desc）"
            if kw:
                hits.append({"keyword": nm, "soulmark": [_soulmark_brief(s) for s in filt(kw)[:limit]]})
    if tag:
        tg = str(tag).strip()
        cand = []
        for t in g.subjects(RDF.type, SEER.SoulmarkTag):
            if tg == label(t) or tg in label(t):
                cand += list(g.subjects(SEER.soulmarkTag, t))
        if not cand:
            cand = [s for s in allsm if tg in (_txt(s) or "")]
            note = note or "标签没命中，改按效果文本搜"
        hits.append({"tag": tg, "soulmark": [_soulmark_brief(s) for s in filt(cand)[:limit]]})
    out["matches"] = hits
    if note:
        out["note"] = note
    return out


def _buff_brief(s):
    g = graph()
    d = {"id": id_of(s), "tag": _txt(s, SEER.tag), "desc": _txt(s)}
    return {k: v for k, v in d.items() if v not in (None, "")}


def tool_effect(name=None, kind=None, limit=10):
    """战斗效果查询：buff（增益/减益/吸血/减伤）、battle_effect（伤害修正/抵抗）、field_effect（场地）。"""
    g = graph()
    classes = {"buff": SEER.Buff, "battle": SEER.BattleEffect, "field": SEER.FieldEffect}
    if kind:
        k = str(kind).strip().lower()
        k = {"buff": "buff", "增益": "buff", "减益": "buff", "battle": "battle",
             "battle_effect": "battle", "伤害": "battle", "field": "field", "场地": "field"}.get(k)
        if k is None:
            return {"error": f"未知 kind：{kind}（用 buff / battle / field）"}
        classes = {k: classes[k]}
    total = sum(1 for c in classes.values() for _ in g.subjects(RDF.type, c))
    if not total:
        return {"error": "本体未含战斗效果个体：需先跑 ingest_effects.py 并重跑 sync.py --merge-only"}
    try:
        limit = max(1, min(int(limit), 60))
    except Exception:
        limit = 10
    out = {"query": {"name": name, "kind": kind}, "total": total}

    if not name:
        cnt = {ln(c): sum(1 for _ in g.subjects(RDF.type, c)) for c in classes.values()}
        out["counts"] = cnt
        # 高频 tag 概览（buff）
        if SEER.Buff in classes.values():
            tc = {}
            for s in g.subjects(RDF.type, SEER.Buff):
                t = _txt(s, SEER.tag)
                if t:
                    tc[t] = tc.get(t, 0) + 1
            out["topBuffTags"] = sorted(({"tag": k, "count": v} for k, v in tc.items()),
                                        key=lambda x: -x["count"])[:20]
        out["hint"] = "传 name（效果名/关键词）检索；kind 可限定 buff / battle / field"
        return out

    nm = str(name).strip()
    res = {}
    for key, cls in classes.items():
        rows = []
        for s in g.subjects(RDF.type, cls):
            text = " ".join(filter(None, [label(s), _txt(s), _txt(s, SEER.name) or ""]))
            if nm in text:
                rows.append(s)
        if rows:
            # 确定性排序：tag 与查询完全一致的排前面，其余按 seerapi id 升序。
            # 不排序时顺序取决于 rdflib 内部迭代，同一查询在合并前后会给出不同首条（曾致回归用例抖动）。
            def _ord(s):
                tag = _txt(s, SEER.tag)
                exact = 0 if tag == nm else 1
                try:
                    sid = int(id_of(s) or 0)
                except Exception:       # noqa: BLE001
                    sid = 0
                return (exact, sid)
            rows.sort(key=_ord)
            if key == "buff":
                res[key] = [_buff_brief(s) for s in rows[:limit]]
            else:
                res[key] = [{"id": id_of(s), "label": label(s), "desc": _txt(s)} for s in rows[:limit]]
    out["matches"] = res or None
    if not res:
        out["hint"] = f"『{nm}』在 buff/battle_effect/field_effect 的名称与描述里都没命中"
    return out


# ---------------- 工具实现 ----------------

def tool_nick(name):
    g = graph()
    seen, out = set(), []
    for s, o in g.subject_objects(SKOS.altLabel):
        if str(o) == name and s not in seen:
            seen.add(s)
            out.append(pet_brief(s))
    if not out:  # 回退：label 精确匹配 / seerapi id（禁止子串，避免"伊芙"错配"伊芙莉莎"）
        for s in g.subjects(RDF.type, SEER.Pet):
            labels = [str(o) for o in g.objects(s, RDFS.label)]
            if name == id_of(s) or name in labels:
                if s not in seen:
                    seen.add(s)
                    out.append(pet_brief(s))
    res = {"query": name, "matches": out}
    # 阵容（Lineup）：名字不是单只精灵时（如「星巴克」是一套组合），给出成员与用法
    for lin in g.subjects(RDF.type, SEER.Lineup):
        labs = [str(o) for o in g.objects(lin, RDFS.label)] + \
               [str(o) for o in g.objects(lin, SKOS.altLabel)]
        if name in labs:
            res.setdefault("lineups", []).append({
                "id": str(lin).split("#")[-1],
                "label": label(lin),
                "members": [label(p) for p in g.objects(lin, SEER.lineupMember)],
                "member_ids": [id_of(p) for p in g.objects(lin, SEER.lineupMember)],
                "note": _txt(lin, SEER.lineupNote),
            })
    return res


DIFF_IRI = {
    "简单": PVE.diff_easy, "easy": PVE.diff_easy, "1": PVE.diff_easy,
    "困难": PVE.diff_normal, "normal": PVE.diff_normal, "2": PVE.diff_normal,
    "地狱": PVE.diff_hard, "hard": PVE.diff_hard, "3": PVE.diff_hard,
}


def find_factor(name):
    g = graph()
    for f in g.subjects(RDF.type, SEER.Factor):
        if name in label(f) or name == ln(f):
            return f
    return None


ENEMY_FIELDS = ["bossHp", "bossTrait", "clearsBuff", "stealsBuff", "clearsPP",
                "turnFixedDamage", "rawCap", "rawCapMode", "immunePanelOver", "shield",
                "multiLife", "immuneSpecial", "immunePhysical", "onlyCrit", "alwaysCrit",
                "selfBuffPerTurn", "debuffUsPerTurn", "control", "dodge",
                "bossAtkScale", "bossDefScale", "bossIsSinglePet"]

_RACE_FIELDS = [("hp", SEER.baseHp), ("atk", SEER.baseAtk), ("def", SEER.baseDef),
                ("spAtk", SEER.baseSpAtk), ("spDef", SEER.baseSpDef), ("spd", SEER.baseSpd)]


def enemy_brief(enemy):
    g = graph()
    d = {"label": label(enemy)}
    tc = g.value(enemy, PVE.bossTypeCombination)
    if tc:
        d["type"] = type_name(tc)
    for f in ENEMY_FIELDS:
        v = g.value(enemy, PVE[f])
        if v is not None:
            d[f] = pyval(v)
    bp = g.value(enemy, PVE.bossSpecies)
    if bp:
        race = {}
        for k, pred in _RACE_FIELDS:
            v = g.value(bp, pred)
            if v is not None:
                race[k] = pyval(v)
        d["bossPet"] = {"id": id_of(bp), "label": label(bp), "race": race}
    cb = [{"id": id_of(p), "label": label(p)} for p in g.objects(enemy, PVE.counteredBy)]
    if cb:
        d["counteredBy"] = cb
    src = g.value(enemy, RDFS.comment)
    if src:
        d["source"] = str(src)
    # 只增：机制文本命中具体异常状态名时追加 statusDetail；没命中就不加这个字段
    sd = status_detail_from_text(str(g.value(enemy, PVE.bossTrait) or ""))
    if sd:
        d["statusDetail"] = sd
    return d


def tool_boss(factor, difficulty):
    g = graph()
    fac = find_factor(factor)
    if fac is None:
        return {"error": f"未找到因子：{factor}"}
    diff = DIFF_IRI.get(difficulty)
    if diff is None:
        return {"error": f"未知难度：{difficulty}（用 简单/困难/地狱 或 easy/normal/hard）"}

    stages = []
    for st in g.objects(fac, SEER.hasStage):
        if g.value(st, PVE.difficulty) != diff:
            continue
        n = pyval(g.value(st, PVE.stageNumber))
        en = g.value(st, PVE.hasEnemy)
        row = {"stage": n, "label": label(st),
               "boss": enemy_brief(en) if en else None}
        # 只增（不改变既有键的语义/顺序）：原始机制文本 + 结构化异常状态明细。
        # 约定：每关恒有 traits（str，可为 ""）与 statusDetail（list，可为 []），无命中时给 []。
        trait_text = str(g.value(en, PVE.bossTrait) or "") if en is not None else ""
        row["traits"] = trait_text
        row["statusDetail"] = status_detail_from_text(trait_text)
        stages.append(row)
    stages.sort(key=lambda x: (x["stage"] if isinstance(x["stage"], int) else 0))

    banned = []
    for fd in g.subjects(RDF.type, PVE.FactorDifficulty):
        if g.value(fd, PVE.forFactor) == fac and g.value(fd, PVE.difficulty) == diff:
            banned = [{"id": id_of(p), "label": label(p)} for p in g.objects(fd, PVE.bannedPet)]

    return {"factor": label(fac), "difficulty": difficulty,
            "stages": stages, "bannedPet": banned}


ROLE_IRI = {
    "attacker": PVE.attacker, "强攻": PVE.attacker, "秒杀": PVE.attacker, "输出": PVE.attacker,
    "support": PVE.support, "辅助": PVE.support,
    "tank": PVE.tank, "站场": PVE.tank, "坦克": PVE.tank,
    "reflect": PVE.reflect, "弹伤": PVE.reflect, "反伤": PVE.reflect,
    "firstStrike": PVE.firstStrike, "必先": PVE.firstStrike, "先制": PVE.firstStrike,
    "finisher": PVE.finisher, "补刀": PVE.finisher, "收尾": PVE.finisher,
    # 站场的细分机制（子类）。查 tank 时会自动扩展到这些子类。
    "免伤站场": PVE["免伤站场"], "护盾站场": PVE["护盾站场"],
    "高防站场": PVE["高防站场"], "磨血站场": PVE["磨血站场"],
}


def _role_expand(r):
    """把角色类展开成「自身 + 所有 rdfs:subClassOf 后代」。"""
    g = graph()
    subs = {}
    for s, o in g.subject_objects(RDFS.subClassOf):
        subs.setdefault(o, set()).add(s)
    out, stack = {r}, [r]
    while stack:
        cur = stack.pop()
        for s in subs.get(cur, ()):
            if s not in out:
                out.add(s)
                stack.append(s)
    return out


def tool_role(role):
    r = ROLE_IRI.get(role)
    if r is None:
        return {"error": f"未知定位：{role}（attacker/support/tank/reflect/firstStrike，或 免伤站场/护盾站场/高防站场/磨血站场）"}
    g = graph()
    roles = _role_expand(r)
    seen, pets = set(), []
    for rr in sorted(roles, key=str):
        for p in g.subjects(PVE.hasRole, rr):
            if p in seen:
                continue
            seen.add(p)
            b = pet_brief(p)
            if rr != r:
                b["站场子类"] = label(rr)
            pets.append(b)
    return {"role": ln(r), "pets": pets, "expanded": [ln(x) for x in sorted(roles, key=str)]}


import type_multiplier as tm


def split_type(s):
    """把 '机械战斗'/'机械·战斗'/'机械/战斗'/['机械','战斗'] 拆成单属性名列表。"""
    if isinstance(s, (list, tuple)):
        names = [str(x) for x in s]
    else:
        s = str(s).strip()
        for sep in ["/", "·", "＋", "+", "-", "、", "／"]:
            if sep in s:
                names = [x for x in [t.strip() for t in s.split(sep)] if x]
                break
        else:
            names = [s]
    # 若整串仍未拆开（“机械战斗”），用已知属性名贪心前缀切分
    resolved = []
    for t in names:
        t2 = t.rstrip("系")
        if t2 in tm.NAME2EID:
            resolved.append(t2)
            continue
        # 贪心切分：优先匹配更长的已知属性名
        parts, i = [], 0
        known = sorted(tm.NAME2EID, key=len, reverse=True)
        while i < len(t2):
            hit = None
            for k in known:
                if t2.startswith(k, i):
                    hit = k
                    break
            if not hit:
                break
            parts.append(hit)
            i += len(hit)
        if parts and i == len(t2):
            resolved.extend(parts)
        else:
            resolved.append(t2)  # 未知，交给 by_names 报 None
    return resolved


def tool_mult(skill_type, boss_type):
    a = split_type(skill_type)
    d = split_type(boss_type)
    m = tm.by_names(a, d)
    if m is None:
        return {"error": f"无法解析属性：攻={skill_type} 守={boss_type}",
                "attackElements": a, "defendElements": d}
    return {
        "skillType": skill_type, "bossType": boss_type,
        "attackElements": a, "defendElements": d,
        "multiplier": m,
        "stab": "本系判定=宠物属性组合与技能属性组合【集合完全相等】时 ×1.5；双属性精灵需双属性技能才吃本系。",
    }


DIFF_CN = {"easy": "简单", "normal": "困难", "hard": "地狱", "简单": "简单", "困难": "困难", "地狱": "地狱"}


def tool_ban(factor, difficulty):
    g = graph()
    fac = find_factor(factor)
    if fac is None:
        # 因子不在本体的 33 个 abox 里时，回退到 plan 层读 SSOT 的 ban 文本
        try:
            import plan as _p
            doc = _p.load_doc(factor, DIFF_CN.get(difficulty, difficulty))
            if doc and doc.get("ban"):
                return {"factor": factor, "difficulty": difficulty, "bannedPet": doc["ban"],
                        "note": "SSOT 文本禁用表(非本体 seerapiId)"}
            return {"factor": factor, "difficulty": difficulty, "bannedPet": []}
        except Exception as e:
            return {"error": f"未找到因子：{factor} ({e})"}
    diff = DIFF_IRI.get(difficulty)
    if diff is None:
        return {"error": f"未知难度：{difficulty}"}
    banned = []
    for fd in g.subjects(RDF.type, PVE.FactorDifficulty):
        if g.value(fd, PVE.forFactor) == fac and g.value(fd, PVE.difficulty) == diff:
            banned = [{"id": id_of(p), "label": label(p)} for p in g.objects(fd, PVE.bannedPet)]
    return {"factor": label(fac), "difficulty": difficulty, "bannedPet": banned}


def tool_plan(factor, difficulty, stage):
    try:
        import plan as _p
    except Exception as e:
        return {"error": f"plan 模块不可用：{e}"}
    r = _p.plan(factor, DIFF_CN.get(difficulty, difficulty), int(stage))
    # 精简 R1 整块里的 mech 原始 slug 与冗余字段，保留可读性
    r1 = r.get("r1_exact")
    if isinstance(r1, dict):
        r["r1_exact"] = {k: r1[k] for k in ("doc_id", "factor", "difficulty", "ban", "tids", "stages") if k in r1}
    return r


def tool_stats():
    import json as _j
    p = os.path.join(HERE, "..", "kb", "stats.json").replace("\\", "/")
    try:
        st = _j.load(open(p, encoding="utf-8"))
    except Exception as e:
        return {"error": f"stats 不可用：{e}"}
    # 只增：control 项追加 by_status 细分（sleep n=? / 害怕 n=? …）。原 n / df_pct 不动，
    # 其它键不动；本体没有异常状态模块时这一整段直接跳过，输出与旧版逐字节一致。
    df = st.get("df")
    if isinstance(df, dict) and isinstance(df.get("control"), dict):
        try:
            bs, note = _control_by_status()
        except Exception:
            bs, note = {}, None
        if bs:
            df["control"]["by_status"] = bs
            df["control"]["by_status_note"] = note
    return {"default_mechs": st.get("default_mechs"), "cold_start_hints": st.get("cold_start_hints"), "df": st.get("df")}


# =============== 玩家装备 / 套装（seer-game.ttl 的 PlayerEquip / Suit / SuitBonus） ===============
# 只新增：不改任何既有工具的函数体与返回结构。本体没有装备个体时，本工具返回空集 + 说明。
PART_ALIAS = {
    "头部": "equippart_0", "头": "equippart_0", "head": "equippart_0", "0": "equippart_0",
    "眼部": "equippart_1", "眼": "equippart_1", "eye": "equippart_1", "1": "equippart_1",
    "腰部": "equippart_2", "腰": "equippart_2", "waist": "equippart_2", "2": "equippart_2",
    "手部": "equippart_3", "手": "equippart_3", "hand": "equippart_3", "3": "equippart_3",
    "足部": "equippart_4", "脚": "equippart_4", "foot": "equippart_4", "4": "equippart_4",
    "背景": "equippart_5", "bg": "equippart_5", "5": "equippart_5",
    "坐骑": "equippart_6", "mount": "equippart_6", "6": "equippart_6",
}
_SIX_GEAR = [("atk", "bonusAtk"), ("def", "bonusDef"), ("sp_atk", "bonusSpAtk"),
             ("sp_def", "bonusSpDef"), ("spd", "bonusSpd"), ("hp", "bonusHp")]


def _gear_match(classes, text):
    """套装/部件名匹配：精确 > 前缀 > 子串；同分时有 bonus 的优先。禁止空串子串匹配。"""
    g = graph()
    text = (text or "").strip()
    if not text:
        return []
    hits = []
    for cls in classes:
        for s in g.subjects(RDF.type, cls):
            labs = [str(o) for o in g.objects(s, RDFS.label)]
            if text in labs:
                score = 3
            elif any(l.startswith(text) for l in labs):
                score = 2
            elif any(text in l for l in labs if l and l != "None"):
                score = 1
            else:
                continue
            hasb = (g.value(s, SEER.suitBonus) is not None
                    or g.value(s, SEER.equipBonus) is not None)
            if hasb:
                score += 0.5
            hits.append((score, cls, s))
    hits.sort(key=lambda x: (-x[0], label(x[2])))
    return hits


def _num(v):
    """接口里 speed 等字段是 float32 落库，会带 5.199999809265137 这类噪声；展示层收敛。"""
    if isinstance(v, float):
        if abs(v - round(v)) < 1e-4:
            return int(round(v))
        return round(v, 3)
    return v


def _bonus_dict(bonus):
    """SuitBonus / EquipBonus 个体 -> dict（不含 raw JSON，只给结构化值 + 原文 desc）。"""
    g = graph()
    if bonus is None:
        return None
    d = {}
    desc = g.value(bonus, SEER.bonusDesc)
    if desc is not None:
        d["desc"] = str(desc)
    attrs = {}
    for k, prop in _SIX_GEAR:
        v = g.value(bonus, SEER[prop])
        if v is not None:
            attrs[k] = _num(pyval(v))
    if attrs:
        d["attribute"] = attrs
        pv = g.value(bonus, SEER.bonusPercent)
        if pv is not None:
            d["attribute"]["percent"] = pyval(pv)
        tv = g.value(bonus, SEER.bonusTotal)
        if tv is not None:
            d["attribute"]["total"] = _num(pyval(tv))
    oa = {}
    for k, prop in (("hit_rate", "otherHitRate"), ("dodge_rate", "otherDodgeRate"),
                    ("crit_rate", "otherCritRate")):
        v = g.value(bonus, SEER[prop])
        if v is not None:
            oa[k] = pyval(v)
    if oa:
        d["otherAttribute"] = oa
    ee = g.value(bonus, SEER.bonusEffect)
    if ee is not None:
        eff = {"id": id_of(ee)}
        args = g.value(bonus, SEER.eidArgs)
        if args is not None:
            try:
                eff["args"] = __import__("json").loads(str(args))
            except Exception:
                eff["args"] = str(args)
        d["effect"] = eff
    eid_raw = g.value(bonus, SEER.effectivePetId)
    eps = [{"id": id_of(p), "label": label(p)} for p in g.objects(bonus, SEER.effectiveForPet)]
    if eps:
        d["effectiveForPet"] = eps
    if eid_raw is not None:
        try:
            d["effectivePetId"] = __import__("json").loads(str(eid_raw))
        except Exception:
            d["effectivePetId"] = str(eid_raw)
    elif eps:
        d["effectivePetId"] = [e["id"] for e in eps]
    return d or None


def _equip_brief(s):
    g = graph()
    d = {"id": id_of(s), "label": label(s)}
    pt = g.value(s, SEER.hasPart)
    if pt is not None:
        d["part"] = label(pt)
    sp = g.value(s, SEER.equipSpeed)
    if sp is not None:
        d["speed"] = _num(pyval(sp))
    pk = g.value(s, SEER.pkAttribute)
    if pk is not None:
        try:
            d["pk"] = __import__("json").loads(str(pk))
        except Exception:
            d["pk"] = str(pk)
    su = g.value(s, SEER.belongsToSuit)
    if su is not None:
        d["suit"] = label(su)
    oc = g.value(s, SEER.hasOccasion)
    if oc is not None:
        d["occasion"] = label(oc)
    b = _bonus_dict(g.value(s, SEER.equipBonus))
    if b:
        d["bonus"] = b
    return d


def _suit_brief(s, limit_parts=10):
    g = graph()
    parts = list(g.subjects(SEER.belongsToSuit, s))
    if not parts:
        parts = list(g.objects(s, SEER.suitEquips))
    parts = sorted(parts, key=lambda p: (label(g.value(p, SEER.hasPart) or p), label(p)))
    d = {"id": id_of(s), "label": label(s), "partCount": len(parts),
         "parts": [_equip_brief(p) for p in parts[:limit_parts]]}
    ts = g.value(s, SEER.transformSuit)
    if ts is not None:
        d["transform"] = pyval(ts)
    cm = g.value(s, RDFS.comment)
    if cm is not None:
        txt = str(cm)
        d["suitDesc"] = txt.split(" | ")[0]
    b = _bonus_dict(g.value(s, SEER.suitBonus))
    if b:
        d["bonus"] = b
    return d


def tool_gear(query=None, part=None, pet=None, limit=5):
    """玩家装备/套装查询。参数名用 query 以免与本体里的 name 概念混淆（MCP 暴露为 name）。"""
    g = graph()
    if query is None and part is None and pet is None:
        return {"error": "至少给 name（套装/部件名）、part（部位）或 pet（精灵）之一"}
    try:
        limit = int(limit)
    except Exception:
        limit = 5
    limit = max(1, min(limit, 50))

    out = {"query": {"name": query, "part": part, "pet": pet}, "notes": []}
    parts_out, suits_out, equips_out, matches = [], [], [], []

    if not any(s for s in g.subjects(RDF.type, SEER.PlayerEquip)) and \
       not any(s for s in g.subjects(RDF.type, SEER.Suit)):
        return {"error": "本体未含玩家装备/套装个体：需先跑 ingest_gear.py 并重跑 sync.py --merge-only",
                "query": out["query"]}

    # 1) 名字匹配（套装 + 部件）
    if query:
        for score, cls, s in _gear_match([SEER.Suit, SEER.PlayerEquip], query):
            kind = "suit" if cls == SEER.Suit else "equip"
            matches.append({"kind": kind, "id": id_of(s), "label": label(s),
                            "match": {3.5: "exact+bonus", 3: "exact", 2.5: "prefix+bonus",
                                      2: "prefix", 1.5: "substring+bonus",
                                      1: "substring"}.get(score, "substring"),
                            "hasBonus": (g.value(s, SEER.suitBonus) is not None
                                         or g.value(s, SEER.equipBonus) is not None)})
        # 套装结果按 limit 展开；同名部件一并给
        for m in matches:
            if len(suits_out) >= limit and len(equips_out) >= limit:
                break
            node = SEER[f"suit_{m['id']}"] if m["kind"] == "suit" else SEER[f"equip_{m['id']}"]
            if m["kind"] == "suit" and len(suits_out) < limit:
                suits_out.append(_suit_brief(node, limit))
            elif m["kind"] == "equip" and len(equips_out) < limit:
                equips_out.append(_equip_brief(node))
        if not matches:
            out["notes"].append(f"『{query}』在套装/部件名里没有命中（精确/前缀/子串都不匹配）")

    # 2) 部位过滤
    if part:
        pi = PART_ALIAS.get(str(part).strip().lower().replace("部", "").strip() + "部") \
            or PART_ALIAS.get(str(part).strip().lower()) or PART_ALIAS.get(str(part).strip())
        if pi is None:
            out["notes"].append(f"未知部位『{part}』；可用 头部/眼部/腰部/手部/足部/背景/坐骑")
        else:
            pt = SEER[pi]
            eqs = sorted(g.subjects(SEER.hasPart, pt), key=lambda x: label(x))
            out["part"] = {"label": label(pt), "count": len(eqs)}
            if query:
                eqs = [e for e in eqs if any(m["id"] == id_of(e) for m in matches)]
            equips_out = [x for x in (_equip_brief(e) for e in eqs[:limit]) if x]
            if not query:
                out["equips"] = equips_out

    # 3) 精灵 -> 专属生效套装
    if pet:
        pids = []
        for m in tool_nick(str(pet)).get("matches") or []:
            pids.append(str(m.get("id")))
        if str(pet).strip().isdigit():
            pids.append(str(pet).strip())
        # 补漏：effective_pets 里存的是"形态 id"（如 谱尼=300），与昵称解析结果（圣灵谱尼=5000）
        # 可能不是同一个个体；只有 4 个套装带该字段，直接回扫比猜更准。
        for bs in g.subjects(RDF.type, SEER.SuitBonus):
            rawids = g.value(bs, SEER.effectivePetId)
            if rawids is None:
                continue
            try:
                cand = __import__("json").loads(str(rawids))
            except Exception:
                continue
            for pid in cand or []:
                pl = label(SEER[f"pet_{pid}"])
                if pl and str(pet) in pl and str(pid) not in pids:
                    pids.append(str(pid))
        if not pids:
            out["notes"].append(f"精灵『{pet}』解析不到 seerapiId，无法查专属套装")
        else:
            hit_suits = []
            for pid in pids:
                for bs in g.subjects(SEER.effectiveForPet, SEER[f"pet_{pid}"]):
                    for su in g.subjects(SEER.suitBonus, bs):
                        if su not in hit_suits:
                            hit_suits.append(su)
            suits_out = [_suit_brief(s, limit) for s in hit_suits[:limit]]
            out["pet"] = {"query": pet, "ids": pids}
            if not hit_suits:
                out["notes"].append("该精灵没有『仅对它生效』的套装（481 套装里只有 4 个有 effective_pets）")
        out["notes"].append("精灵装备（刻印）不属本工具，见 seer:Mintmark / seer:hasMintmark")

    if suits_out:
        out["suits"] = suits_out
    if equips_out:
        out["equips"] = equips_out
    if matches:
        out["matches"] = matches[:10]
    out["count"] = {"suits": len(suits_out), "equips": len(equips_out), "matches": len(matches)}
    out["notes"].append("pk_attribute=战队保卫战老玩法加成，非PVE；speed=玩家跑图移动速度，非精灵速度")
    return out


def tool_gear_dispatch(**kw):
    """MCP 参数名是 name；内部函数用 query（避免与 RDF 的 label/name 概念混淆）。"""
    if "name" in kw:
        kw["query"] = kw.pop("name")
    return tool_gear(**kw)


def _skill_brief(s):
    g = graph()
    out = {"name": label(s), "id": id_of(s)}
    for prop, key in (("power", "威力"), ("priority", "先制"), ("maxPP", "PP"), ("accuracy", "命中"),
                      ("mustHit", "必中"), ("atkNum", "连击"), ("skillCategory", "类别")):
        v = g.value(s, SEER[prop])
        if v is not None:
            out[key] = pyval(v)
    tc = g.value(s, SEER.skillType)
    if tc is not None:
        out["属性"] = type_name(tc) or label(tc)
    effs = []
    for be in g.objects(s, SEER.hasSkillEffect):
        e = {"info": _txt(be, SEER.effectInfo)}
        args = g.value(be, SEER.effectArgs)
        if args is not None:
            e["args"] = str(args)
        bf = g.value(be, SEER.bossEffective)
        if bf is not None:
            e["boss有效"] = "是" if pyval(bf) else "否"
        effs.append({k: v for k, v in e.items() if v is not None})
    if effs:
        out["效果"] = effs
    pets = [label(p) for p in g.subjects(SEER.hasSkill, s)]
    if pets:
        out["学习精灵"] = pets[:12]
    return out


def tool_skill(name=None, pet=None, limit=8):
    """技能查询：name → 威力/先制/PP/必中/属性/效果全文；pet → 该精灵的技能表（按先制、威力排序）。
    本体没有就明确返回 miss，提示走 onto_fill.py 回填。"""
    g = graph()
    if pet:
        pet_node = None
        for p in g.subjects(RDF.type, SEER.Pet):
            lb = label(p) or ""
            if lb == pet or pet in lb or id_of(p) == str(pet):
                pet_node = p
                break
        if pet_node is None:
            return {"miss": f"本体没有精灵「{pet}」", "next": f'python onto_fill.py --pet "{pet}"'}
        skills = list(g.objects(pet_node, SEER.hasSkill))
        if not skills:
            return {"pet": pet, "miss": "该精灵在本体里没有技能表（只入库了面板/魂印）",
                    "next": f'python onto_fill.py --pet "{pet}"'}
        rows = [_skill_brief(s) for s in skills]
        rows.sort(key=lambda r: (-(r.get("先制") or 0), -(r.get("威力") or 0)))
        return {"pet": pet, "count": len(rows), "skills": rows[:limit]}

    if name:
        pat = str(name).strip()
        hits = []
        for s in g.subjects(RDF.type, SEER.Skill):
            lb = label(s)
            if lb and (pat in lb or pat == id_of(s)):
                hits.append(s)
        if not hits:
            return {"miss": f"本体没有技能「{pat}」", "next": f'python onto_fill.py --skill "{pat}"'}
        return {"count": len(hits), "skills": [_skill_brief(s) for s in hits[:limit]]}

    n = len(set(g.subjects(RDF.type, SEER.Skill)))
    n_eff = len(set(g.subjects(RDF.type, SEER.SkillEffect)))
    n_link = len(set(g.subjects(SEER.hasSkill, None)))
    o = {}
    for s in g.subjects(RDF.type, SEER.Skill):
        v = g.value(s, SEER.priority)
        if v is not None:
            o[str(int(v))] = o.get(str(int(v)), 0) + 1
    return {"Skill": n, "SkillEffect": n_eff, "有技能表的精灵": n_link,
            "先制分布": dict(sorted(o.items(), key=lambda kv: -int(kv[0]))[:6])}


TOOLS = [
    {"name": "skill", "description": "技能查询（本体优先）：name → 威力/先制/PP/命中/必中/连击/属性/技能类别/效果全文/boss是否有效；pet → 该精灵全部技能（按先制、威力排序）。返回 miss 表示本体缺这块，需要先回填。",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "技能名（可子串）或 seerapi 技能 id，如 神灵之触、碧水映星天"},
         "pet": {"type": "string", "description": "精灵名或 id，如 圣灵谱尼、4955"},
         "limit": {"type": "integer", "description": "最多返回条数，默认 8、上限 40"}},
         "required": []}},
    {"name": "nick", "description": "昵称消歧：把「潘/火潘/草潘/冰潘/王哈/艾欧/鲁斯王/丽莎/村长/眠酱」等社区简称解析成规范精灵(id+属性+定位+机制备注)。",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string", "description": "社区简称 / 精灵名 / seerapi ID"}}, "required": ["name"]}},
    {"name": "boss", "description": "查某因子某难度的逐关 Boss 硬门(属性/血量/免疫特攻/只吃暴击/多命/固伤/裸伤上限/面板免疫/护盾/清PP/吸强/消强/控场/闪避等) + 每关反制精灵 counteredBy + 禁用表。",
     "inputSchema": {"type": "object", "properties": {
         "factor": {"type": "string", "description": "因子/精灵名，如 佩洛瑟斯、伊塔回溯型"},
         "difficulty": {"type": "string", "description": "简单/困难/地狱 或 easy/normal/hard"}},
         "required": ["factor", "difficulty"]}},
    {"name": "role", "description": "按 PVE 定位列出精灵池：attacker=强攻 / support=辅助 / tank=站场 / reflect=弹伤 / firstStrike=必先。",
     "inputSchema": {"type": "object", "properties": {"role": {"type": "string", "description": "attacker/support/tank/reflect/firstStrike 或中文"}}, "required": ["role"]}},
    {"name": "mult", "description": "属性克制倍率：技能属性(攻方) vs Boss属性(守方)，支持单/双属性与组合写法，返回精确倍率 + 本系 STAB(×1.5) 规则。",
     "inputSchema": {"type": "object", "properties": {
         "skill_type": {"type": "string", "description": "攻击技能属性，如 机械 / 机械战斗 / 机械·战斗 / 圣灵自然"},
         "boss_type": {"type": "string", "description": "Boss 属性组合，如 机械 / 机械战斗"}},
         "required": ["skill_type", "boss_type"]}},
    {"name": "ban", "description": "查因子×难度的禁用精灵表(bannedPet)。",
     "inputSchema": {"type": "object", "properties": {
         "factor": {"type": "string"}, "difficulty": {"type": "string", "description": "简单/困难/地狱 或 easy/normal/hard"}},
         "required": ["factor", "difficulty"]}},
    {"name": "plan", "description": "因子关打法检索：R1 精确(因子×难度整块) + R2/R3 相似关召回(机制/数值模板) + RRF 融合 + 硬门缺口标注；无攻略时给冷启动先验。",
     "inputSchema": {"type": "object", "properties": {
         "factor": {"type": "string", "description": "因子/精灵名"},
         "difficulty": {"type": "string", "description": "简单/困难/地狱 或 easy/normal/hard"},
         "stage": {"type": "integer", "description": "关号 1..5"}},
         "required": ["factor", "difficulty", "stage"]}},
    {"name": "status", "description": "查异常状态（睡眠/害怕/麻痹/烧伤/中毒/冰封/焚烬/石化/诅咒/疲惫…）的完整属性：官方效果、是否控场、持续回合、施加条件与概率、解除方式、免疫规则、会施加它的技能/精灵、会施加它的 Boss 关卡、反制建议。name 可传状态名或俗称（冰冻/毒）或技能名（昏睡之舞）或精灵名；category 可传 控制/持续伤害/削弱/附属/限制。",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "状态名/俗称/技能名/精灵名，如 睡眠、冰冻、昏睡之舞、佩洛瑟斯"},
         "category": {"type": "string", "description": "控制 / 持续伤害 / 削弱 / 附属 / 限制（或 control/dot/weaken/aux/restrict）"}},
         "required": []}},
    {"name": "soulmark", "description": "魂印查询：精灵名/ID → 该精灵的魂印全文（效果文本/标签/PVE 是否生效/是否进阶态）；tag（吸血/减伤/固伤…）→ 该标签下所有魂印；pve_only=true 只留 PVE 生效项；不给参数 → 标签总览。魂印是 PVE 配队的关键被动，常决定某只精灵能不能站场。",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "精灵名/seerapi ID（如 帝皇之御、星光·鲁斯王）；也可传效果关键词"},
         "tag": {"type": "string", "description": "魂印标签，如 吸血、减伤、固伤、续航"},
         "pve_only": {"type": "boolean", "description": "只返回 PVE 生效（pve_effective=true 或未标注）的魂印"},
         "limit": {"type": "integer", "description": "最多返回条数，默认 8、上限 40"}},
         "required": []}},
    {"name": "effect", "description": "战斗效果查询：buff(增益/减益/吸血/减伤/异常)、battle_effect(伤害修正与抵抗)、field_effect(场地)。传 name 用名称/关键词检索（如 吸血、减伤、暴击），不传则给计数与高频 buff 标签总览。用于判断 Boss 的『每回合××』到底是什么效果。",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "效果名或关键词，如 吸血、减伤、免疫、固伤"},
         "kind": {"type": "string", "description": "buff / battle / field（或 增益/伤害/场地）"},
         "limit": {"type": "integer", "description": "每类最多返回条数，默认 10、上限 60"}},
         "required": []}},
    {"name": "stats", "description": "机制占比统计：默认机制(必先/封属/固伤等) + 每关 top 非默认机制(冷启动先验) + 各机制 df。",
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "gear", "description": "玩家装备/套装查询：按套装名(支持社区简称 银翼/漆黑/天人/耀世/典狱长)、部件名、部位(头部/眼部/腰部/手部/足部/背景/坐骑)或精灵查套装与部件；返回套装加成(六维+是否百分比+官方原文desc)、部件列表(部位/移动速度/PK加成)、专属生效精灵。注意：pk_attribute 是战队保卫战老玩法加成、非PVE；speed 是玩家跑图移动速度、非精灵速度；精灵刻印不属本工具。",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "套装名/部件名/简称，如 漆黑、银翼、天人、六界战甲、漆黑之刺"},
         "part": {"type": "string", "description": "头部/眼部/腰部/手部/足部/背景/坐骑 或 head/eye/waist/hand/foot/bg/mount"},
         "pet": {"type": "string", "description": "精灵名或 seerapi ID，查仅对该精灵生效的套装"},
         "limit": {"type": "integer", "description": "每个列表最多返回条数，默认 5、上限 50"}},
         "required": []}},
]

HANDLERS = {"nick": tool_nick, "boss": tool_boss, "role": tool_role, "mult": tool_mult,
            "ban": tool_ban, "plan": tool_plan, "stats": tool_stats, "status": tool_status,
            "gear": tool_gear_dispatch, "soulmark": tool_soulmark, "effect": tool_effect,
            "skill": tool_skill}


def call_tool(name, args):
    fn = HANDLERS.get(name)
    if fn is None:
        raise ValueError(f"未知工具 {name}")
    # 只喂声明的参数，忽略多余，避免意外
    return fn(**args)


# ---------------- MCP stdio 主循环 ----------------

def handle(msg):
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}
    try:
        if method == "initialize":
            ver = params.get("protocolVersion", "2024-11-05")
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": ver,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "seer-kb", "version": "1.0.0"}}}
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            try:
                result = call_tool(name, args)
                text = json.dumps(result, ensure_ascii=False, indent=2)
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": text}], "isError": False}}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text", "text": f"ERROR: {e}"}], "isError": True}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
    return None  # 其它通知，不回应


def main():
    sys.stderr.write("[seer-kb] MCP stdio server starting\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()