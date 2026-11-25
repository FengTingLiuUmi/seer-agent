# -*- coding: utf-8 -*-
"""onto_fill.py —— 本体缺口的按需回填（先查本体 → 缺了报告 → 查 API → 写回本体）

原则（用户定的）：
  1) 统一先查本体；本体没有 → 明确报告"本体缺 X"
  2) 再查 SeerAPI 拿准确数据
  3) 把结果补进本体（seer-miss-abox.ttl），下次直接命中

用法：
  python onto_fill.py --skill "神灵之触"          # 技能 + 其全部效果
  python onto_fill.py --skill-id 31140
  python onto_fill.py --pet "圣灵谱尼"            # 精灵 + 它的全部技能 + hasSkill
  python onto_fill.py --pet-id 4955
  python onto_fill.py --pet "圣灵谱尼" --dry       # 只报告，不写文件

写回目标：seer-miss-abox.ttl（与已有内容合并，幂等）。sync.py 会把它并进 seer-all.owl。
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from rdflib import Graph, Literal, Namespace, RDF, RDFS, XSD

BASE = "https://api.seerapi.com/v1/"
SEER = Namespace("http://example.org/seer#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "seer-miss-abox.ttl")

CAT = {1: "物理攻击", 2: "特殊攻击", 4: "属性技能"}


def get_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seer-fill/0.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:          # noqa: BLE001
            last = e
            time.sleep(0.4 * (i + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def find_id(resource, name):
    d = get_json(BASE + resource + "?name=" + urllib.parse.quote(name))
    hits = [x for x in d.get("results", []) if x.get("id")]
    if not hits:
        return None
    return hits[0]["id"]


# ---- 技能/属性组合缓存 + 并发预取 ----------------------------------------------
# 每个技能详情要单独请求 skill/{id}；一只精灵十几个技能串行要 30s+。
# 这里做两层：进程内 dict + 磁盘 json，配合线程池预取，批量回填才跑得动。
CACHE_PATH = os.path.join(HERE, "skill-cache.json")
_CACHE = None
_LOCK = threading.Lock()
_DIRTY = [False]
WORKERS = 12


def _load_cache():
    global _CACHE
    if _CACHE is None:
        if os.path.exists(CACHE_PATH):
            try:
                _CACHE = json.load(open(CACHE_PATH, encoding="utf-8"))
            except Exception:               # noqa: BLE001
                _CACHE = {}
        else:
            _CACHE = {}
    return _CACHE


def _cache_get(key):
    return _load_cache().get(key)


def _cache_put(key, val):
    with _LOCK:
        _load_cache()[key] = val
        _DIRTY[0] = True


def flush_cache():
    if _DIRTY[0]:
        with _LOCK:
            tmp = CACHE_PATH + ".tmp"
            json.dump(_CACHE, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, CACHE_PATH)
            _DIRTY[0] = False


def get_cached(url):
    hit = _cache_get(url)
    if hit is not None:
        return hit
    val = get_json(url)
    _cache_put(url, val)
    return val


def prefetch(urls, workers=None):
    """并发把还没缓存的 url 拉下来。失败的留给后面按需重试。"""
    urls = [u for u in dict.fromkeys(urls) if _cache_get(u) is None]
    if not urls:
        return 0
    workers = workers or WORKERS
    ok = 0

    def one(u):
        try:
            return u, get_json(u)
        except Exception:                   # noqa: BLE001
            return u, None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for u, val in ex.map(one, urls):
            if val is not None:
                _cache_put(u, val)
                ok += 1
    return ok


def label(name):
    return Literal(str(name), lang="zh")


def boss_flag(text):
    t = (text or "").lower()
    if "boss有效" in t:
        return True
    if "boss无效" in t:
        return False
    return None


def map_tc(g, tid, name=None):
    s = SEER[f"tc_{tid}"]
    g.add((s, RDF.type, SEER.TypeCombination))
    g.add((s, SEER.seerapiId, Literal(str(tid))))
    if name:
        g.add((s, RDFS.label, label(name)))
    return s


def map_skill(g, sk):
    sid = sk.get("id")
    s = SEER[f"skill_{sid}"]
    g.add((s, RDF.type, SEER.Skill))
    g.add((s, SEER.seerapiId, Literal(str(sid))))
    g.add((s, RDFS.label, label(sk.get("name"))))
    for key, prop in (("power", "power"), ("priority", "priority"), ("max_pp", "maxPP"),
                      ("accuracy", "accuracy"), ("must_hit", "mustHit"), ("atk_num", "atkNum")):
        v = sk.get(key)
        if v is not None:
            if isinstance(v, bool):
                g.add((s, SEER[prop], Literal(v)))
            else:
                g.add((s, SEER[prop], Literal(int(v))))
    cat = (sk.get("category") or {}).get("id")
    if cat in CAT:
        g.add((s, SEER.skillCategory, Literal(CAT[cat])))
    t = sk.get("type") or {}
    if t.get("id") is not None:
        tname = t.get("name") or get_cached(BASE + f"element_type_combination/{t['id']}").get("name")
        g.add((s, SEER.skillType, map_tc(g, t["id"], tname)))
    fx = 0
    for i, e in enumerate(sk.get("skill_effect") or []):
        if not isinstance(e, dict):
            continue
        be = SEER[f"skillfx_{sid}_{i}"]
        g.add((be, RDF.type, SEER.SkillEffect))
        g.add((s, SEER.hasSkillEffect, be))
        et = (e.get("effect") or {}).get("id")
        if et is not None:
            st = SEER[f"setype_{et}"]
            g.add((st, RDF.type, SEER.SkillEffectType))
            g.add((st, SEER.seerapiId, Literal(str(et))))
            g.add((be, SEER.effectTypeOf, st))
        if e.get("args"):
            g.add((be, SEER.effectArgs, Literal(json.dumps(e["args"]))))
        if e.get("info"):
            g.add((be, SEER.effectInfo, Literal(str(e["info"]))))
        bf = boss_flag(" ".join(str(x) for x in [e.get("analyze_info"), e.get("info")] if x))
        if bf is not None:
            g.add((be, SEER.bossEffective, Literal(bf, datatype=XSD.boolean)))
        fx += 1
    if sk.get("info"):
        g.add((s, SEER.desc, Literal(str(sk["info"]))))
    return s, fx


def map_pet(g, p, with_skills=True):
    pid = p.get("id")
    s = SEER[f"pet_{pid}"]
    g.add((s, RDF.type, SEER.Pet))
    g.add((s, SEER.seerapiId, Literal(str(pid))))
    g.add((s, RDFS.label, label(p.get("name"))))
    t = p.get("type") or {}
    if t.get("id"):
        g.add((s, SEER.hasTypeCombination, map_tc(g, t["id"], t.get("name"))))
    bs = p.get("base_stats") or {}
    for key, prop in (("hp", "baseHp"), ("atk", "baseAtk"), ("def", "baseDef"),
                      ("sp_atk", "baseSpAtk"), ("sp_def", "baseSpDef"), ("spd", "baseSpd"),
                      ("total", "total")):
        v = bs.get(key)
        if v is not None:
            g.add((s, SEER[prop], Literal(int(v))))
    n_sk = 0
    if with_skills:
        sids = []
        for ref in p.get("skill") or []:
            sk_ref = (ref or {}).get("skill") or ref or {}
            if sk_ref.get("id"):
                sids.append(sk_ref["id"])
        prefetch([BASE + f"skill/{x}" for x in sids])
        for sid in sids:
            detail = get_cached(BASE + f"skill/{sid}")
            if not detail:
                continue
            map_skill(g, detail)
            g.add((s, SEER.hasSkill, SEER[f"skill_{sid}"]))
            n_sk += 1
    return s, n_sk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill")
    ap.add_argument("--skill-id", type=int)
    ap.add_argument("--pet")
    ap.add_argument("--pet-id", type=int)
    ap.add_argument("--pet-ids", help="逗号分隔的多个 pet id，一次写盘（批量回填用）")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if not any([a.skill, a.skill_id, a.pet, a.pet_id, a.pet_ids]):
        print(__doc__)
        return 2

    g = Graph()
    g.bind("seer", SEER)
    if os.path.exists(OUT):
        g.parse(OUT, format="turtle")
    before = len(g)
    report = []

    if a.skill or a.skill_id:
        sid = a.skill_id or find_id("skill", a.skill)
        if not sid:
            print(f"MISS skill {a.skill}: SeerAPI 也查不到这个名字")
            return 3
        sk = get_cached(BASE + f"skill/{sid}")
        _, fx = map_skill(g, sk)
        report.append(f"skill {sk.get('name')}({sid}) 威力={sk.get('power')} 先制={sk.get('priority')} "
                      f"PP={sk.get('max_pp')} 效果={fx}")

    if a.pet or a.pet_id:
        pid = a.pet_id or find_id("pet", a.pet)
        if not pid:
            print(f"MISS pet {a.pet}: SeerAPI 也查不到这个名字")
            return 3
        p = get_cached(BASE + f"pet/{pid}")
        _, n = map_pet(g, p)
        report.append(f"pet {p.get('name')}({pid}) 技能={n}")

    if a.pet_ids:
        ids = [t.strip() for t in a.pet_ids.split(",") if t.strip()]
        prefetch([BASE + f"pet/{t}" for t in ids])      # 先把精灵详情并发拉全
        for tok in ids:
            try:
                pid = int(tok)
                p = get_cached(BASE + f"pet/{pid}")
                _, n = map_pet(g, p)
                report.append(f"pet {p.get('name')}({pid}) 技能={n}")
            except Exception as e:      # noqa: BLE001
                report.append(f"pet {tok} FAIL {type(e).__name__}: {e}")

    added = len(g) - before
    for line in report:
        print(line)
    print(f"新增三元组 {added}（{before} -> {len(g)}）")
    flush_cache()
    if a.dry:
        print("dry-run：未写文件")
        return 0
    os.makedirs(HERE, exist_ok=True)
    g.serialize(destination=OUT, format="turtle")
    print(f"已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())