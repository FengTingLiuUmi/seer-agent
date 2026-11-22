# -*- coding: utf-8 -*-
"""ontology.py —— seer-query 的「本体」后端。

精灵名 / ID 消歧从 seer-factor-kb 本体（seer-all.owl）取，不再走 seerapi / BattleData 名反查。
只读、零写；本体不可用时返回 None（调用方降级处理，不做子串误配）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # .../seer/seer-rebuild/seer_rebuild

SEER_NS = "http://example.org/seer#"
PVE_NS = "http://example.org/seer/pve#"


def kb_root() -> Path | None:
    """定位 seer-factor-kb 工作区（可用环境变量 SEER_KB_PATH 覆盖）。"""
    env = os.environ.get("SEER_KB_PATH")
    cands = [Path(env)] if env else []
    cands.append(_HERE.parents[1] / "seer-factor-kb")  # 默认：seer 项目下的 seer-factor-kb
    for c in cands:
        try:
            if (c / "ontology" / "seer-all.owl").is_file():
                return c.resolve()
        except OSError:
            continue
    return None


def _ensure_paths(root: Path) -> None:
    for sub in (root / "ontology", root / ".pylibs"):
        s = str(sub)
        if s not in sys.path:
            sys.path.insert(0, s)


_G, _G_MTIME, _G_ROOT = None, None, None


def _load():
    """惰性加载本体图（按 mtime 自动重载）；本体/rdflib 不可用返回 None。"""
    global _G, _G_MTIME, _G_ROOT
    root = kb_root()
    if root is None:
        return None
    try:
        from rdflib import Graph, Namespace
    except Exception:
        return None
    _ensure_paths(root)
    owl = root / "ontology" / "seer-all.owl"
    try:
        mt = owl.stat().st_mtime
    except OSError:
        return None
    if _G is None or mt != _G_MTIME or root != _G_ROOT:
        g = Graph()
        g.parse(str(owl), format="xml")
        _G, _G_MTIME, _G_ROOT = g, mt, root
    return _G, Namespace(SEER_NS), Namespace(PVE_NS)


def _label(g, node):
    from rdflib import RDFS
    for o in g.objects(node, RDFS.label):
        return str(o)
    return None


def _id(g, pet, SEER):
    v = g.value(pet, SEER.seerapiId)
    return str(v) if v is not None else None


def _brief(g, pet, SEER, PVE):
    from rdflib import RDFS
    types = []
    for tc in g.objects(pet, SEER.hasTypeCombination):
        els = []
        for e in g.objects(tc, SEER.combinationOf):
            lb = _label(g, e)
            if lb:
                els.append(lb)
        types.append("/".join(els) if els else None)
    types = [t for t in types if t]
    roles = [str(o) for o in g.objects(pet, PVE.hasRole) if str(o)]
    note = g.value(pet, RDFS.comment)
    return {
        "id": _id(g, pet, SEER),
        "label": _label(g, pet),
        "type": types,
        "roles": [r.rsplit("#", 1)[-1] for r in roles],
        "note": str(note) if note else "",
    }


def pet_lookup(query):
    """精确消歧（altLabel / label / seerapiId，不做子串，避免"伊芙"误配"伊芙莉莎"）。

    返回 {"query": q, "matches": [brief...]}；本体不可用返回 None。
    """
    from rdflib import SKOS
    loaded = _load()
    if loaded is None:
        return None
    g, SEER, PVE = loaded
    q = str(query).strip()
    seen, out = set(), []
    for s, o in g.subject_objects(SKOS.altLabel):
        if str(o) == q and s not in seen:
            seen.add(s)
            out.append(_brief(g, s, SEER, PVE))
    if not out:
        for s in g.subjects(None, None):  # 兜底遍历 Pet（本体规模可控，惰性单次）
            if s in seen:
                continue
            if str(s).rsplit("#", 1)[-1].startswith("pet_") and (
                str(_id(g, s, SEER)) == q or _label(g, s) == q
            ):
                seen.add(s)
                out.append(_brief(g, s, SEER, PVE))
    return {"query": q, "matches": out}


def pet_name(pet_id):
    """按 seerapiId 反查规范名；找不到返回 None。"""
    return pet_lookup(pet_id)