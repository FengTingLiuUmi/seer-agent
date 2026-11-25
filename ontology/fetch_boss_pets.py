# -*- coding: utf-8 -*-
"""从 SeerAPI 拉取「每关 Boss 是哪只精灵」的权威映射 → scrape/factor-boss-design.json。

产出（每个因子）：
  seer_factor_id / design_id / target_pet_id
  stages[easy|normal|hard][1..5] = {boss_pet_id, is_single_pet}
  banned_pets[easy|normal|hard] = [pet_id]   # 权威 Ban 表（比论坛抽取更可靠）

幂等：随时重跑覆盖。名称匹配：我们的因子名 与 SeerAPI `<名>因子` 做归一（去·去空格去"因子"）。
运行：PYTHONUTF8=1 PYTHONPATH=<workspace> python fetch_boss_pets.py
"""
import asyncio, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SCRAPE = os.path.join(HERE, "..", "scrape").replace("\\", "/")
KB = os.path.join(HERE, "..", "kb").replace("\\", "/")

from seerapi import SeerAPI  # noqa: E402


def norm(s):
    # 只保留 CJK + 字母数字，吞掉所有中点/空格/标点变体（·・∙/. 等），再剥「因子」后缀
    s = str(s).replace("因子", "")
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


async def main():
    api = SeerAPI()
    facs = []
    async for f in api.list("factor"):
        facs.append(f)
    seer_by_norm = {}
    for f in facs:
        seer_by_norm.setdefault(norm(f.name), []).append(f)

    with open(f"{KB}/docs/catalog.json", encoding="utf-8") as f:
        cat = json.load(f)
    our_names = sorted({c["factor"] for c in cat})

    alias = {}
    ap = f"{SCRAPE}/factor_alias.json"
    if os.path.exists(ap):
        with open(ap, encoding="utf-8") as f:
            alias = json.load(f).get("map", {})
    alias_norm = {norm(k): norm(v) for k, v in alias.items()}

    # 名称覆写：我们的因子名 → SeerAPI 因子名（别名/简称/错别字/形态前缀差异）
    NAME_OVERRIDE = {
        "北鸟": "万里春·北鸟因子", "卓尔布": "浮掠双刃·卓尔布因子", "哲利斯": "嫉妒·哲利斯因子",
        "圣心女孩·卡托娜": "卡托娜因子", "塞弥丝珂": "塞弥斯珂因子", "库拉姆斯": "库莱姆斯因子",
        "桑多姆": "雷瀑飞雪·桑多姆因子", "欧根尼克": "无限·欧根尼克因子", "沙弑·吉拉": "吉拉因子",
        "混灵·莱因哈特": "混灵·莱茵哈特因子", "溯洄·拉伯克": "溯洄·拉伯克因子", "环·零": "环·零因子",
        "莫伊莱": "命运之轮·莫伊莱因子", "裁罪魔剪塞泽斯": "裁罪魔剪·塞泽丝因子", "西叶": "枫落殇·西叶因子",
        "霍瑞洛吉": "霍瑞洛吉因子",
    }

    out, missing, ambig, no_design = {}, [], [], []
    for name in our_names:
        key = alias_norm.get(norm(name), norm(name))
        cands = seer_by_norm.get(norm(NAME_OVERRIDE.get(name, key)))
        if not cands:
            cands = seer_by_norm.get(key)
        if not cands:
            missing.append(name)
            continue
        if len(cands) > 1:
            ambig.append((name, [c.name for c in cands]))
        f = cands[0]
        did = f.design.id if getattr(f, "design", None) else None
        if did is None:
            # 无标准 5 关设计（旧/下架因子）：只确定第5关=本体 target pet，前4关宁缺毋滥
            entry = {"seer_factor_id": f.id, "design_id": None, "design_missing": True}
            if getattr(f, "pet", None):
                entry["target_pet_id"] = f.pet.id
                for lv in ("easy", "normal", "hard"):
                    entry.setdefault("stages", {})[lv] = {"5": {"boss_pet_id": f.pet.id}}
            else:
                entry["stages"] = {}
            out[name] = entry
            no_design.append(name)
            continue
        try:
            d = await api.get("factor_design", did)
        except Exception as e:  # noqa: BLE001
            missing.append((name, str(e)))
            continue
        entry = {"seer_factor_id": f.id, "design_id": did}
        if getattr(f, "pet", None):
            entry["target_pet_id"] = f.pet.id
        stages, banned = {}, {}
        for diff in d.difficulties:
            lv = diff.level
            if getattr(diff, "banned_pets", None):
                banned[lv] = [bp.id for bp in diff.banned_pets]
            smap = {}
            for i, t in enumerate(diff.tasks, 1):
                smap[str(i)] = {"boss_pet_id": t.boss_pet.id, "is_single_pet": bool(t.is_single_pet)}
            stages[lv] = smap
        entry["stages"] = stages
        if banned:
            entry["banned_pets"] = banned
        out[name] = entry

    result = {"factors": out, "missing": missing, "ambiguous": ambig, "design_missing": no_design}
    fp = f"{SCRAPE}/factor-boss-design.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"SeerAPI 因子总数 = {len(facs)}；匹配 = {len(out)}；缺 = {len(missing)}；歧义 = {len(ambig)}；无设计 = {len(no_design)}")
    for m in missing[:30]:
        print("  缺:", m)
    for a in ambig[:20]:
        print("  歧义:", a)
    for nd in no_design:
        print("  无设计(仅本体关 boss):", nd)
    print("写出", fp)


if __name__ == "__main__":
    asyncio.run(main())