# -*- coding: utf-8 -*-
"""把本体缺少的 Boss 精灵物种抓下来 → scrape/pets-boss-supp.json（供 build_supp 补进本体）。

输入：scrape/factor-boss-design.json（每关 boss_pet_id）
流程：去重后的 boss_pet_id → 若本体(seer-all.owl)没有对应 seer:Pet → SeerAPI 抓 name/type/base_stats。
产出：pets-boss-supp.json { pets: [{seerapiId,name,type:[单/双属性名],base_stats:{hp,atk,...}}] }
幂等：重复运行覆盖。运行：PYTHONUTF8=1 python fetch_boss_pet_supp.py
"""
import asyncio, json, os, re
from rdflib import Graph, RDF, Namespace
from seerapi import SeerAPI

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SCRAPE = os.path.join(HERE, "..", "scrape").replace("\\", "/")
ONT = HERE
SEER = Namespace("http://example.org/seer#")


async def main():
    api = SeerAPI()
    with open(f"{SCRAPE}/factor-boss-design.json", encoding="utf-8") as f:
        design = json.load(f).get("factors", {})
    ids = set()
    for e in design.values():
        if e.get("target_pet_id"):
            ids.add(int(e["target_pet_id"]))
        for lv, sm in (e.get("stages") or {}).items():
            for sid, t in sm.items():
                if t.get("boss_pet_id"):
                    ids.add(int(t["boss_pet_id"]))
        for lv, bans in (e.get("banned_pets") or {}).items():
            ids.update(int(b) for b in bans)

    g = Graph()
    g.parse(f"{ONT}/seer-all.owl", format="xml")
    existing = {str(g.value(p, SEER.seerapiId)) for p in g.subjects(RDF.type, SEER.Pet) if g.value(p, SEER.seerapiId) is not None}
    missing = sorted(str(i) for i in ids if str(i) not in existing)
    print(f"唯一 boss/banned pet id = {len(ids)}；本体已有 = {len(ids) - len(missing)}；缺失 = {len(missing)}")

    pets, comb_cache = [], {}
    fails = []
    for pid in missing:
        try:
            p = await api.get("pet", int(pid))
        except Exception as e:  # noqa: BLE001
            fails.append((pid, str(e)[:80]))
            continue
        name = p.name
        types = []
        cid = p.type.id if getattr(p, "type", None) else None
        if cid is not None:
            if cid not in comb_cache:
                try:
                    tc = await api.get("element_type_combination", cid)
                    comb_cache[cid] = tc.name
                except Exception:  # noqa: BLE001
                    comb_cache[cid] = None
            if comb_cache.get(cid):
                types = [x for x in comb_cache[cid].split(" ") if x]
        rec = {"seerapiId": int(pid), "name": name, "type": types}
        bs = getattr(p, "base_stats", None)
        if getattr(bs, "atk", None) is not None:
            rec["base_stats"] = {"hp": bs.hp, "atk": bs.atk, "def": bs.def_,
                                 "sp_atk": bs.sp_atk, "sp_def": bs.sp_def, "spd": bs.spd}
        pets.append(rec)

    fp = f"{SCRAPE}/pets-boss-supp.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump({"pets": pets}, f, ensure_ascii=False, indent=1)
    print(f"抓到缺失宠物 = {len(pets)}，失败 = {len(fails)}")
    for f in fails[:20]:
        print("  失败:", f)
    print("写出", fp)


if __name__ == "__main__":
    asyncio.run(main())