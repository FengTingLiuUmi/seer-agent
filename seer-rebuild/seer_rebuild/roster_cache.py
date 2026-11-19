"""账号打手库缓存：加载 / 查询（JOIN 三层：species 静态 + 个体动态 + 机制标签）。

数据文件：
  data/account_pets.json   物种静态（type/种族值，seerapi，由 init/refresh 生成）
  data/roster_cache.json   个体动态（catch_time -> level + 装备技能，2301 生成）
  domain_knowledge/knowledge.db  机制标签（role/soulmark/skill tags）

用法：
  from seer_rebuild.roster_cache import load, station_tanks, attackers
  pets = load()
  station_tanks(pets, lv=90) -> 站场手（不要求克制，只要能活）
  attackers(pets, stype='冰', lv=100) -> 该单系1.5×打手
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "account_pets.json"
DYNAMIC = ROOT / "data" / "roster_cache.json"

# 站场/生存机制标签（不要求克制）
SURVIVAL_TAGS = {"减伤", "吸血", "免疫攻击", "保命", "免异常", "免下降", "回血", "护盾", "护罩"}


def load_static() -> list[dict]:
    if not STATIC.exists():
        return []
    return json.loads(STATIC.read_text(encoding="utf-8"))


def load_dynamic() -> dict[int, dict]:
    if not DYNAMIC.exists():
        return {}
    return json.loads(DYNAMIC.read_text(encoding="utf-8"))


def _db_tags() -> dict[int, tuple[set[str], set[str]]]:
    try:
        from .sqlite_kb import SqliteKB
        kb = SqliteKB()
        out = {}
        for r in kb.con.execute("SELECT * FROM pets").fetchall():
            sp = r["species_id"]
            out[sp] = (set(json.loads(r["role_tags"] or "[]")),
                       set(json.loads(r["soulmark_tags"] or "[]")))
        kb.close()
        return out
    except Exception:
        return {}


def load() -> list[dict]:
    """合并三层成一个可用列表。"""
    static = {p["species_id"]: p for p in load_static()}
    dyn = load_dynamic()
    tags = _db_tags()
    out = []
    for sp, p in static.items():
        roles, soul = tags.get(sp, (set(), set()))
        indivs = dyn.get(str(sp), [])
        entry = dict(p)
        entry["role_tags"] = sorted(roles)
        entry["soulmark_tags"] = sorted(soul)
        entry["individuals"] = indivs
        entry["level"] = max((i.get("level") or 0 for i in indivs), default=0)
        entry["skills"] = sorted({s for i in indivs for s in (i.get("skills") or [])})
        out.append(entry)
    return out


def _single_types(p: dict) -> set[str]:
    return set((p.get("type") or "").replace("，", " ").split())


def station_tanks(pets: list[dict], *, lv: int = 90) -> list[dict]:
    """站场手：满级 + 带生存机制标签（不要求克制）。"""
    out = []
    for p in pets:
        if p["level"] < lv:
            continue
        allt = set(p["role_tags"]) | set(p["soulmark_tags"])
        if allt & SURVIVAL_TAGS:
            out.append(p)
    return sorted(out, key=lambda x: -(x.get("hp") or 0))


def attackers(pets: list[dict], *, stype: str | None = None, lv: int = 90) -> list[dict]:
    """强攻手：满级；可按单系筛选（克制提前算好传入）。"""
    out = []
    for p in pets:
        if p["level"] < lv:
            continue
        if stype is not None and stype not in _single_types(p):
            continue
        if max(p.get("atk") or 0, p.get("sp_atk") or 0) < 130:
            continue
        out.append(p)
    return sorted(out, key=lambda x: -max(x.get("atk") or 0, x.get("sp_atk") or 0))


if __name__ == "__main__":
    pets = load()
    print("缓存物种数:", len(pets), "已缓存个体数:", sum(len(p["individuals"]) for p in pets))
    print("\n== 站场手(满级+生存机制) ==")
    for p in station_tanks(pets):
        print('  %d %-14s type=%-10s hp=%s atk=%s spa=%s 魂印标签=%s' % (
            p["species_id"], p["name"], p["type"], p.get("hp"), p.get("atk"), p.get("sp_atk"),
            "、".join(p["soulmark_tags"])))