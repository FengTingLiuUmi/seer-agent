# -*- coding: utf-8 -*-
"""ingest_gear.py —— 配装 ABox：suit(套装) / title(称号) / nature(性格) / fire(火，手工)。
数据源：SeerAPI list（这三个资源的 list 直接返回完整对象）。
映射：suit -> label+comment(suit_desc/套装效果)；title -> label+comment(desc)+attr_bonus(数值)；
      nature -> label+comment(des)+attributes(数值)；fire -> 手工个体。
"""
import json, os, time, urllib.request
from rdflib import Graph, Namespace, RDF, RDFS, Literal

BASE = "https://api.seerapi.com/v1/"
SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "seer-gear-abox.ttl")

g = Graph()
g.bind("seer", SEER)
_stats = {}


def gj(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seer-gear/0.1"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.0 + i)


def list_all(resource):
    items, url = [], f"{BASE}{resource}?limit=100"
    while url:
        d = gj(url)
        if not d:
            break
        items += d.get("results", [])
        nxt = d.get("next")
        if isinstance(nxt, str):
            url = nxt
        elif isinstance(nxt, dict) and nxt.get("offset") is not None:
            url = f"{BASE}{resource}?limit=100&offset={nxt['offset']}"
        else:
            url = None
    return items


def raw(v):
    return Literal(json.dumps(v, ensure_ascii=False, sort_keys=True)) if v is not None else None


def bump(k):
    _stats[k] = _stats.get(k, 0) + 1


def main():
    # 1) nature（25）
    for n in list_all("nature"):
        sid = n.get("id")
        s = SEER[f"nature_{sid}"]
        g.add((s, RDF.type, SEER.Nature))
        if sid is not None:
            g.add((s, SEER.seerapiId, Literal(str(sid))))
        g.add((s, RDFS.label, Literal(str(n.get("name")), lang="zh")))
        if n.get("attributes"):
            g.add((s, SEER.attributes, raw(n["attributes"])))
        cm = " ".join(str(x) for x in [n.get("des"), n.get("des2")] if x)
        if cm:
            g.add((s, RDFS.comment, Literal(cm, lang="zh")))
        bump("Nature")

    # 2) title（597）：全量但只存 name/desc/attr_bonus
    for t in list_all("title"):
        sid = t.get("id")
        s = SEER[f"title_{sid}"]
        g.add((s, RDF.type, SEER.Title))
        if sid is not None:
            g.add((s, SEER.seerapiId, Literal(str(sid))))
        g.add((s, RDFS.label, Literal(str(t.get("name")), lang="zh")))
        if t.get("attr_bonus"):
            g.add((s, SEER.attrBonus, raw(t["attr_bonus"])))
        if t.get("desc"):
            g.add((s, RDFS.comment, Literal(str(t["desc"]), lang="zh")))
        bump("Title")

    # 3) suit（481）：全量，存名 + suit_desc + 套装效果描述
    for su in list_all("suit"):
        sid = su.get("id")
        s = SEER[f"suit_{sid}"]
        g.add((s, RDF.type, SEER.Suit))
        if sid is not None:
            g.add((s, SEER.seerapiId, Literal(str(sid))))
        g.add((s, RDFS.label, Literal(str(su.get("name")), lang="zh")))
        parts = [su.get("suit_desc")]
        b = su.get("bonus") or {}
        if b.get("desc"):
            parts.append("套装效果:" + b["desc"])
        if b.get("attribute"):
            parts.append(json.dumps(b["attribute"], ensure_ascii=False))
        cm = " | ".join(str(x) for x in parts if x)
        if cm:
            g.add((s, RDFS.comment, Literal(cm, lang="zh")))
        bump("Suit")

    # 4) 火（SeerAPI 无资源，手工）
    fires = [
        ("fire_lvh", "绿火", "自动放的全局火：续命/命中/基础增益"),
        ("fire_jh", "金火", "借用增伤火焰（帖子里叫「借金火」）"),
        ("fire_xxx", "星星领火", "领的增伤火（thread-3409 提到可免领）"),
    ]
    for fid, nm, cm in fires:
        s = SEER[fid]
        g.add((s, RDF.type, SEER.Fire))
        g.add((s, RDFS.label, Literal(nm, lang="zh")))
        g.add((s, RDFS.comment, Literal(cm, lang="zh")))
        bump("Fire")

    g.serialize(OUT, format="turtle")
    print("完成 ->", OUT)
    print("三元组 =", len(g))
    for k in sorted(_stats):
        print(f"  {k}: {_stats[k]}")


if __name__ == "__main__":
    main()