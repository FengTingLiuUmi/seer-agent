# -*- coding: utf-8 -*-
"""泛化默认方案（表姐强攻）：帝皇之御 31505 守御八方自爆 + 克制 Boss 属性的持有强攻手。

这是「最省事」的通用模板：多数多精灵关不需要照抄 SSOT 的特定增伤链，
有表姐 + 属性克制的强攻手就能一波必先必暴打过去。SSOT 特定阵容只作兜底/增伤链。

选强攻手规则（近似、保守）：
  持有 ∩ 定位=attacker(强攻/输出/秒杀) ∩ (精灵本系属性 ∈ 克制面[技能属性克 boss 的集合])
  按只数从多到少取前 4 个候选；首发帝皇之御，后 2 次技能由 top1/top2 打（必先必暴）。

单精灵关无法自爆，表姐强攻不适用，单独标注。

运行：PYTHONPATH=.pylibs;kb;ontology;player python player/generalize.py 飞鱼骑士 地狱
"""
import os
import sys

from rdflib import Namespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "kb"))
sys.path.insert(0, os.path.join(ROOT, "ontology"))

import player_cache as PC  # noqa: E402
import plan as P  # noqa: E402
from build_prompt import pet_meta, ROLE_CN  # noqa: E402

MIMI = "753949294"
TABLE_ID = "3512"   # 帝皇之御（表姐）
TABLE_SKILL = 31505  # 守御八方：攻击技能，不吃封属；整队后 2 次技能必先+必暴，跨换宠


def main():
    factor, difficulty = sys.argv[1], sys.argv[2]
    doc = P.load_doc(factor, difficulty)
    cps = P._counter_profiles()
    meta = pet_meta()

    conn = PC.connect()
    owned = set(PC.species_owned(conn, MIMI))
    attackers = []
    for sp in owned:
        m = meta.get(sp)
        if not m or "attacker" not in m["roles"]:
            continue
        attackers.append({
            "sp": sp, "name": m["name"], "type": m["type"],
            "roles": [ROLE_CN.get(x, x) for x in m["roles"]],
            "n": PC.count_species(conn, MIMI, sp),
        })
    table_n = PC.count_species(conn, MIMI, TABLE_ID)
    conn.close()

    attackers.sort(key=lambda a: (-a["n"], a["name"]))
    print(f"# {factor} · {difficulty}  泛化默认方案（表姐强攻）")
    print(f"# 持有 帝皇之御(表姐) ×{table_n}；持有 attacker 强攻手 {len(attackers)} 只\n")

    for st in doc["stages"]:
        stage = st["stage"]
        cp = cps.get(f"{factor}#{difficulty}#{stage}", {})
        boss = cp.get("boss_type") or st.get("boss_type")
        counter = set(cp.get("counter") or [])
        single = bool(st.get("boss_is_single_pet")) or ("singlePet" in (st.get("mech") or []))
        hard = st.get("traits")

        picks = [a for a in attackers if set(a["type"]) & counter]
        print(f"== 第{stage}关  Boss={boss}  克制面={sorted(counter)}  "
              f"{'[单精灵]' if single else '[多精灵]'}")
        if not table_n:
            print("  · 无表姐，无可用的「表姐强攻」")
        if single:
            print("  · 单精灵关不能自爆 → 表姐强攻不适用，走单挑池")
            print(f"  · 硬门/威胁：{hard}")
            print()
            continue
        line = f"  · 表姐强攻：帝皇之御 31505 守御八方自爆 → "
        if picks:
            top = picks[:4]
            line += "后两只克制强攻手，候选(按只数)："
            print(line)
            for i, a in enumerate(top, 1):
                print(f"      {i}. {a['name']}  type={a['type']}  {','.join(a['roles'])}  ×{a['n']}")
        else:
            line += "持有池暂无「attacker 且属性克制 boss」的打手 → 换 SSOT 特定阵容/补强攻手"
            print(line)
        print(f"  · 硬门/威胁：{hard}")
        print()


if __name__ == "__main__":
    main()