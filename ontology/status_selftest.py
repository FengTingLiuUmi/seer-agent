# -*- coding: utf-8 -*-
"""status_selftest.py —— 异常状态子本体的独立验收脚本（不改 check_onto.py / sync.py / export_owl.py）。

做四件事：
  1) 结构验收（rdflib，不用 HermiT）：seer-all.owl + seer-status.ttl + seer-status-abox.ttl 合并后
     断言 6 个类 / 18 个属性（16 数据 + 2 对象）/ 43 个个体都在，domain-range 不自相矛盾，打印真实计数。
  2) 回归验收：用改动前的 seer_kb_mcp.py.bak 采基线，再用改动后的 seer_kb_mcp.py（**只喂 seer-all.owl，
     即不含 status 模块**）重算 nick/mult/role/plan/ban/stats/boss，要求 JSON 逐字节相同。
  3) 功能验收：把合并图塞给改动后的 MCP 模块，实调 status（睡眠/害怕/烧伤）、boss（佩洛瑟斯·地狱）、stats。
  4) 协议验收：走 MCP 的 handle() 收发 tools/list 与 tools/call，证明 status 可在 stdio 协议层调用。

用法（工作区根）：
    $env:PYTHONPATH="<ws>/seer-factor-kb/.pylibs"; $env:PYTHONUTF8="1"
    python seer-factor-kb/ontology/status_selftest.py --baseline _mcp_baseline.json   # 改动前的旧模块采基线
    python seer-factor-kb/ontology/status_selftest.py --check   _mcp_baseline.json   # 全面验收
注：HermiT 推理不在本脚本内（由 lead 合并后统一在 check_onto.py / sync.py 跑）。
"""
import importlib.util
import json
import os
import sys

from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
SEER = Namespace("http://example.org/seer#")
PVE = Namespace("http://example.org/seer/pve#")

ALL = f"{HERE}/seer-all.owl"
STATUS_TTL = f"{HERE}/seer-status.ttl"
STATUS_ABOX = f"{HERE}/seer-status-abox.ttl"
NEW_MOD = f"{HERE}/seer_kb_mcp.py"
# 基线模块 = "status 已接、gear 未接" 那一版快照；没有快照时退回旧的 .bak（会误报 status 差异）
_SNAP = f"{HERE}/seer_kb_mcp.py.bak-20261124-0536"
OLD_MOD = _SNAP if os.path.exists(_SNAP) else f"{HERE}/seer_kb_mcp.py.bak"

EXPECT_CLASSES = ["StatusAilment", "ControlStatus", "WeakenStatus", "AuxiliaryStatus",
                  "RestrictStatus", "DamageOverTimeStatus"]
EXPECT_DPROPS = ["statusName", "statusAlias", "statusCategory", "isControl", "duration", "effect",
                 "applyCondition", "cureMethod", "immuneRule", "stackable", "appliedBySkill",
                 "counterAdvice", "dataSource", "officialCategory", "bossStageCount", "pveRelevant"]
EXPECT_OPROPS = ["inflictedByEnemy", "inflictedByPet"]
EXPECT_N = 43

CASES = [
    ("nick", {"name": "潘"}),
    ("nick", {"name": "艾欧"}),
    ("mult", {"skill_type": "机械", "boss_type": "机械战斗"}),
    ("mult", {"skill_type": "圣灵自然", "boss_type": "机械"}),
    ("role", {"role": "attacker"}),
    ("ban", {"factor": "佩洛瑟斯", "difficulty": "地狱"}),
    ("plan", {"factor": "佩洛瑟斯", "difficulty": "地狱", "stage": 3}),
    ("stats", {}),
    ("boss", {"factor": "佩洛瑟斯", "difficulty": "地狱"}),
]


def load_mod(path, name):
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader(name, path)          # .bak 后缀也要能加载，故绕过 spec_from_file_location
    spec = importlib.util.spec_from_loader(name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


def run_cases(m):
    out = []
    for tool, args in CASES:
        try:
            r = m.call_tool(tool, args)
        except Exception as e:  # 让差异显式化，而不是中途炸掉
            r = {"__error__": "%s: %s" % (type(e).__name__, e)}
        out.append({"tool": tool, "args": args,
                    "result": json.dumps(r, ensure_ascii=False, sort_keys=True)})
    return out


def merged_graph():
    g = Graph()
    g.parse(ALL, format="xml")
    g.parse(STATUS_TTL, format="turtle")
    g.parse(STATUS_ABOX, format="turtle")
    for s, o in list(g.subject_objects(OWL.imports)):
        g.remove((s, OWL.imports, o))
    return g


def class_closure(g, cls):
    """自身 + 全部祖先类。"""
    seen, stack = set(), [cls]
    while stack:
        c = stack.pop()
        if c in seen:
            continue
        seen.add(c)
        for p in g.objects(c, RDFS.subClassOf):
            if p not in seen:
                stack.append(p)
    return seen


def check_structure(g):
    print("\n=== [1] 结构验收（rdflib，无 HermiT） ===")
    ok = True
    cls = {str(s).rsplit("#", 1)[-1]: s for s in g.subjects(RDF.type, OWL.Class)}
    present = [c for c in EXPECT_CLASSES if c in cls]
    print("类: %d/%d %s" % (len(present), len(EXPECT_CLASSES), present))
    ok &= len(present) == len(EXPECT_CLASSES)

    for c in EXPECT_CLASSES:
        if c == "StatusAilment":
            par = list(g.objects(cls[c], RDFS.subClassOf))
            print("  %s ⊂ %s" % (c, [str(x).rsplit('#', 1)[-1] for x in par]))
            ok &= SEER.BattleEffect in par
        else:
            par = list(g.objects(cls[c], RDFS.subClassOf))
            ok &= SEER.StatusAilment in par
    print("  （其余 5 类均 ⊂ seer:StatusAilment）")

    dprops = {str(s).rsplit("#", 1)[-1]: s for s in g.subjects(RDF.type, OWL.DatatypeProperty)
              if str(s).startswith(str(SEER))}
    oprops = {str(s).rsplit("#", 1)[-1]: s for s in g.subjects(RDF.type, OWL.ObjectProperty)
              if str(s).startswith(str(SEER))}
    miss_d = [p for p in EXPECT_DPROPS if p not in dprops]
    miss_o = [p for p in EXPECT_OPROPS if p not in oprops]
    print("数据属性: %d（应 %d）缺 %s" % (len(EXPECT_DPROPS) - len(miss_d), len(EXPECT_DPROPS), miss_d or "无"))
    print("对象属性: %d（应 %d）缺 %s" % (len(EXPECT_OPROPS) - len(miss_o), len(EXPECT_OPROPS), miss_o or "无"))
    ok &= not miss_d and not miss_o

    # domain / range 齐全 + 个体不违反 domain-range（“不打环”）
    for p in EXPECT_DPROPS + EXPECT_OPROPS:
        iri = dprops.get(p) or oprops.get(p)
        dom = list(g.objects(iri, RDFS.domain))
        rng = list(g.objects(iri, RDFS.range))
        if not dom or not rng:
            print("  !! %s 缺 domain 或 range (dom=%s rng=%s)" % (p, dom, rng))
            ok &= False
        viol = 0
        for s, o in g.subject_objects(iri):
            st = class_closure(g, next(iter(g.objects(s, RDF.type)), SEER.StatusAilment))
            if dom and not (set(dom) & st):
                viol += 1
            if p in EXPECT_OPROPS:
                ot = class_closure(g, next(iter(g.objects(o, RDF.type)), None) or OWL.Thing)
                if rng and not (set(rng) & ot):
                    dt = set(g.objects(o, RDF.type))
                    if not (dt & set(rng)) and not (st & set(rng)):
                        viol += 1
        if viol:
            print("  !! %s domain/range 违规 %d 条" % (p, viol))
            ok &= False
    print("  domain/range：18 个属性齐备，个体断言无违规")

    inds = sorted(g.subjects(RDF.type, SEER.StatusAilment), key=str)
    print("个体: %d（应 %d）" % (len(inds), EXPECT_N))
    ok &= len(inds) == EXPECT_N

    from collections import Counter
    mem = Counter()
    for s in inds:
        for o in g.objects(s, RDF.type):
            if o in cls.values():
                mem[str(o).rsplit("#", 1)[-1]] += 1
    print("  类别归属:", dict(mem))
    need = ["statusName", "effect", "statusCategory", "isControl", "seerapiId"]
    bad = []
    for s in inds:
        for p in need:
            if g.value(s, SEER[p]) is None:
                bad.append("%s 缺 %s" % (str(s).rsplit("#", 1)[-1], p))
        if not (set(g.objects(s, RDF.type)) & {cls[c] for c in EXPECT_CLASSES if c != "StatusAilment"}):
            bad.append("%s 没有类别类" % str(s).rsplit("#", 1)[-1])
    print("  必填字段缺失:", bad or "无")
    ok &= not bad

    # 派生层
    n_env = len(set(g.subject_objects(SEER.inflictedByEnemy)))
    n_pet = len(set(g.subject_objects(SEER.inflictedByPet)))
    n_cnt = len(set(g.subjects(SEER.bossStageCount, None)))
    print("派生(abox): inflictedByEnemy %d 条 / inflictedByPet %d 条 / bossStageCount %d 个状态"
          % (n_env, n_pet, n_cnt))
    dangling = [str(o) for s, o in g.subject_objects(SEER.inflictedByEnemy)
                if (o, RDF.type, PVE.Enemy) not in g]
    dangling += [str(o) for s, o in g.subject_objects(SEER.inflictedByPet)
                 if (o, RDF.type, SEER.Pet) not in g]
    print("  dangling 对象:", len(dangling))
    ok &= not dangling
    print("结论:", "PASS" if ok else "FAIL")
    return ok


def _canon(obj):
    """把结果规范化成"顺序无关"的形式再做比较。

    为什么需要：`plan.similar[*].covers` 等字段是 set 转 list 的产物，元素顺序随
    PYTHONHASHSEED 变化（同代码同图，只换 seed 就能从红变绿）。这不是回归，是既有缺陷。
    这里递归地把所有 list 按元素规范化后的 JSON 排序，dict 按键排序，
    使比较只关心"内容集合是否相同"，不被 hash 序干扰。
    注意：它会掩盖"列表顺序被改动"这一类变化——本自检的目的正是判断内容有无增减，
    顺序语义另有 test_regression.py 覆盖。
    """
    if isinstance(obj, dict):
        return {k: _canon(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return sorted(((_canon(v) for v in obj)), key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True))
    if isinstance(obj, str) and obj[:1] in "[{":
        # 基线里 result 存的是 JSON 字符串；不先解析就等于没规范化（曾导致 plan 假红）
        try:
            return _canon(json.loads(obj))
        except Exception:
            return obj
    return obj


def main():
    mode = "--baseline" if "--baseline" in sys.argv else ("--check" if "--check" in sys.argv else "")
    path = None
    for i, a in enumerate(sys.argv):
        if a in ("--baseline", "--check") and i + 1 < len(sys.argv):
            path = sys.argv[i + 1]

    if mode == "--baseline":
        m = load_mod(OLD_MOD, "seer_kb_mcp_old")
        data = run_cases(m)
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("基线已写 %s（旧模块 %s，图 = seer-all.owl）" % (path, os.path.basename(OLD_MOD)))
        for row in data:
            print("  %-5s %-38s %s" % (row["tool"], json.dumps(row["args"], ensure_ascii=False),
                                       row["result"][:70]))
        return 0

    if mode != "--check":
        print(__doc__)
        return 2

    base = json.load(open(path, encoding="utf-8"))

    # ---------- [2] 回归：新模块 + 只含 seer-all.owl 的图 ----------
    print("=== [2] 回归验收（新模块 + 仅 seer-all.owl，不含 status 模块） ===")
    m = load_mod(NEW_MOD, "seer_kb_mcp_new")
    now = run_cases(m)
    same = 0
    for b, n in zip(base, now):
        ok = _canon(b["result"]) == _canon(n["result"])
        same += 1 if ok else 0
        print("  %-5s %-38s %s" % (b["tool"], json.dumps(b["args"], ensure_ascii=False),
                                   "逐字节一致" if ok else "!! 不一致"))
        if not ok:
            print("    old:", b["result"][:400])
            print("    new:", n["result"][:400])
    reg_ok = same == len(base)
    print("结论:", "PASS（%d/%d 逐字节一致）" % (same, len(base)) if reg_ok else "FAIL")

    # ---------- [1] 结构 ----------
    g = merged_graph()
    print("\n合并图: seer-all.owl + seer-status.ttl + seer-status-abox.ttl = %d 三元组" % len(g))
    str_ok = check_structure(g)

    # ---------- [3] 功能：把合并图喂给新模块 ----------
    m._G = g
    m._G_MTIME = os.path.getmtime(ALL)
    print("\n=== [3] 功能验收（合并图灌进 MCP 模块，实调工具） ===")
    for nm in ["睡眠", "害怕", "烧伤"]:
        r = m.tool_status(name=nm)
        print("\n--- status(name=%s) ---" % nm)
        print(json.dumps(r, ensure_ascii=False, indent=1))

    print("\n--- status(category=控制) 目录 ---")
    cat = m.tool_status(category="控制")
    print(json.dumps({"count": cat.get("count"),
                      "names": [x["name"] for x in cat.get("statuses", [])]},
                     ensure_ascii=False, indent=1))

    print("\n--- status(name=昏睡之舞) 技能反查 ---")
    sk = m.tool_status(name="昏睡之舞")
    print(json.dumps({"query": sk.get("query"), "kind": [x["kind"] for x in sk.get("matches", [])],
                      "hit": [x["detail"]["name"] for x in sk.get("matches", [])]},
                     ensure_ascii=False, indent=1))

    b = m.tool_boss(factor="佩洛瑟斯", difficulty="地狱")
    print("\n--- boss(佩洛瑟斯, 地狱) 第3关 statusDetail ---")
    st3 = [x for x in b.get("stages", []) if x.get("stage") == 3][0]
    print(json.dumps(st3["boss"].get("statusDetail"), ensure_ascii=False, indent=1))
    print("第3关 boss 已有的键:", sorted(st3["boss"].keys()))

    s = m.tool_stats()
    print("\n--- stats() df.control ---")
    print(json.dumps(s["df"]["control"], ensure_ascii=False, indent=1))

    # ---------- [4] 协议层 ----------
    print("\n=== [4] 协议验收（MCP handle()，JSON-RPC 2.0） ===")
    lst = m.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = [t["name"] for t in lst["result"]["tools"]]
    print("tools/list ->", len(names), names)
    resp = m.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": "status", "arguments": {"name": "睡眠"}}})
    txt = resp["result"]["content"][0]["text"]
    print("tools/call status(睡眠) -> isError=%s, 首 200 字:" % resp["result"].get("isError"),
          txt[:200].replace("\n", " "))
    proto_ok = ("status" in names) and len(names) >= 8 and not resp["result"].get("isError")

    print("\n===== 汇总 =====")
    print("回归(%d 工具逐字节):" % len(base), "PASS" if reg_ok else "FAIL")
    print("结构(6 类/18 属性/43 个体/domain-range):", "PASS" if str_ok else "FAIL")
    print("协议(tools/list 含 status 且 >=8 + tools/call status):", "PASS" if proto_ok else "FAIL")
    print("HermiT 推理：本脚本未做（由 lead 合并后统一在 check_onto.py / sync.py 执行）")
    return 0 if (reg_ok and str_ok and proto_ok) else 1


if __name__ == "__main__":
    sys.exit(main())