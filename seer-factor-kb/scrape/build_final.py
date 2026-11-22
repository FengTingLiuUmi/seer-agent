# -*- coding: utf-8 -*-
"""最终合并：论坛抽取(factors-extracted.json) + B站抽取(factors-bili.json) → factors-final.json。
按「因子名(去空格去·) × 难度」合并；特性以 B站为准，攻略/阵容两源并集。
可随时重跑：B站文件越多，最终表越全。
"""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")

def norm(name):
    return re.sub(r"[·\.\s]+", "", str(name)).strip()

def load(path):
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding="utf-8"))

# 别名表：论坛简称/错写 → B站规范名（见 factor_alias.json 的 _evidence）
ALIAS = {}
ALIAS_DISP = {}
_alias_path = f"{HERE}/factor_alias.json"
if os.path.exists(_alias_path):
    for k, v in json.load(open(_alias_path, encoding="utf-8")).get("map", {}).items():
        ALIAS[norm(k)] = norm(v)
        ALIAS_DISP[norm(k)] = v

def key_of(name):
    k = norm(name)
    return ALIAS.get(k, k)

# 剔除的伪因子（见 factor-excluded.json 的依据）
EXCLUDED = {}
_exp = f"{HERE}/factor-excluded.json"
if os.path.exists(_exp):
    EXCLUDED = {norm(k): v for k, v in (json.load(open(_exp, encoding="utf-8")).get("excluded") or {}).items()}

forum = load(f"{HERE}/factors-extracted.json")
bili = load(f"{HERE}/factors-bili.json")

final = {}  # (norm_name) -> entry

def entry(key, name):
    if key not in final:
        final[key] = {"factor": name, "difficulties": {}, "tids": [], "ban": [], "note": ""}
    return final[key]

def stage_key(difficulty, n):
    return (difficulty, int(n))

def merge_stage(s, src):
    # src 字段并入 s（boss_type/boss_hp 首非空优先；traits/strategies/pets 并集）
    for k in ("boss_type", "boss_hp"):
        if src.get(k) not in (None, "") and k not in s:
            s[k] = src[k]
    s.setdefault("traits", [])
    if src.get("traits") and src["traits"] not in s["traits"]:
        s["traits"].append(src["traits"])
    s.setdefault("strategies", [])
    for x in src.get("strategies", []) or []:
        if x not in s["strategies"]:
            s["strategies"].append(x)
    s.setdefault("pets", [])
    for p in src.get("pets", []) or []:
        if p not in s["pets"]:
            s["pets"].append(p)

# 1) B站（地狱）为准
for e in bili:
    key = key_of(e["factor"])
    if key in EXCLUDED:
        continue
    en = entry(key, e["factor"])
    for t in e.get("tids", []):
        if t not in en["tids"]:
            en["tids"].append(t)
    if e.get("source"):
        src = e["source"] if isinstance(e["source"], list) else [e["source"]]
        en.setdefault("bili_source", []).extend(src)
    for st in e.get("stages", []):
        n = st.get("stage")
        if n is None:
            continue
        s = en["difficulties"].setdefault(("地狱", int(n)), {"stage": int(n), "traits": [], "strategies": [], "pets": []})
        merge_stage(s, st)

# 2) 论坛（覆盖 简单/困难/地狱 的攻略与阵容）
for e in forum:
    key = key_of(e["factor"])
    if key in EXCLUDED:
        continue
    en = entry(key, ALIAS_DISP.get(norm(e["factor"]), e["factor"]))
    for t in e.get("tids", []):
        if t not in en["tids"]:
            en["tids"].append(t)
    for b in e.get("ban", []) or []:
        if b not in en["ban"]:
            en["ban"].append(b)
    dif = e.get("difficulty") or ""
    for st in e.get("stages", []):
        n = st.get("stage")
        if n is None or not dif:
            continue
        s = en["difficulties"].setdefault((dif, int(n)), {"stage": int(n), "traits": [], "strategies": [], "pets": []})
        merge_stage(s, st)
    if e.get("note") and not en["note"]:
        en["note"] = e["note"]

def clean_traits(parts):
    """特性片段去重：拆 ; ； ，去掉完全重复，以及被更长片段完全包含的短片段
    （如 已保留『月亮(强化技能半血以下)』就不必再留裸『月亮』）。"""
    frag = []
    for p in parts:
        # 抽取阶段偶有把列表直接 str() 进 traits 的（如 "['封属']"），先摊平
        if isinstance(p, (list, tuple)):
            items = list(p)
        else:
            sp = str(p).strip()
            if sp.startswith("[") and sp.endswith("]"):
                try:
                    import ast
                    v = ast.literal_eval(sp)
                    items = list(v) if isinstance(v, (list, tuple)) else [sp]
                except Exception:
                    items = [sp]
            else:
                items = re.split(r"[;；]", sp)
        for x in items:
            x = str(x).strip()
            if x and x not in frag:
                frag.append(x)
    keep = []
    for x in sorted(frag, key=len, reverse=True):
        if any(x != y and x in y for y in keep):
            continue
        if x not in keep:
            keep.append(x)
    # 恢复可读顺序：按原出现顺序
    order = {x: i for i, x in enumerate(frag)}
    return sorted(keep, key=lambda x: order[x])


PLACEHOLDER_TYPE = re.compile(r"^(未知|无|不详|不明|\?|N/?A)$", re.I)
PLACEHOLDER_TRAIT = re.compile(r"^(特性)?(未查到|未找到|未知|暂无|无|N/?A)$", re.I)

# 属性名与合法组合（由 ontology/type_multiplier 导出，见 type-vocab.json）
_TV = f"{HERE}/type-vocab.json"
TYPE_NAMES = sorted(json.load(open(_TV, encoding="utf-8"))["names"], key=len, reverse=True) if os.path.exists(_TV) else []
VALID_COMBOS = {"|".join(sorted(c.split("|"))) for c in (json.load(open(_TV, encoding="utf-8"))["combos"] if os.path.exists(_TV) else [])}
# 社区写法 → 规范写法
TYPE_ALIAS = {"飞龙": "飞行龙", "地龙": "地面龙", "飞超能": "飞行超能", "水系": "水", "火系": "火",
              "草系": "草", "冰系": "冰", "电系": "电", "龙系": "龙", "神秘系": "神秘"}


def _segment(s):
    out, i = [], 0
    while i < len(s):
        for n in TYPE_NAMES:
            if s.startswith(n, i):
                out.append(n)
                i += len(n)
                break
        else:
            return None
    return out


def normalize_type(bt):
    """去 ·/空格、套社区别名、校验是否为真实组合；非法则返回 None（该字段省略）。"""
    if not isinstance(bt, str) or not bt.strip():
        return None
    s = bt.replace("·", "").replace(" ", "").strip()
    s = TYPE_ALIAS.get(s, s)
    if not TYPE_NAMES:
        return s
    seg = _segment(s)
    if seg is None or "|".join(sorted(seg)) not in VALID_COMBOS:
        return None
    return s


def sanitize(s):
    """清掉占位文本；boss_type 统一去 ·/空格并校验真实性，非法即省略。"""
    bt = s.get("boss_type")
    if isinstance(bt, str):
        if PLACEHOLDER_TYPE.match(bt.strip()):
            s.pop("boss_type", None)
        else:
            nt = normalize_type(bt)
            if nt:
                s["boss_type"] = nt
            else:
                s.pop("boss_type", None)
    tr = s.get("traits")
    if isinstance(tr, str) and PLACEHOLDER_TRAIT.match(tr.strip()):
        s.pop("traits", None)
    return s


out = []
for key in sorted(final):
    en = final[key]
    stages = []
    for (dif, n) in sorted(en["difficulties"]):
        s = en["difficulties"][(dif, n)]
        s["difficulty"] = dif
        s["stage"] = n
        if s.get("traits"):
            s["traits"] = "; ".join(clean_traits(s["traits"]))
        else:
            s.pop("traits", None)
        for k in ("strategies", "pets"):
            if not s.get(k):
                s.pop(k, None)
        sanitize(s)
        stages.append(s)
    en.pop("difficulties", None)
    en["stages"] = stages
    if not en["tids"]:
        en.pop("tids", None)
    if not en["ban"]:
        en.pop("ban", None)
    if not en["note"]:
        en.pop("note", None)
    out.append(en)

with open(f"{HERE}/factors-final.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

n = len(out)
with_traits = sum(1 for e in out if any("traits" in s for s in e["stages"]))
with_pets = sum(1 for e in out if any("pets" in s for s in e["stages"]))
hard = sum(1 for e in out if any(s["difficulty"] == "地狱" for s in e["stages"]))
print(f"合并因子 = {n}；有特性 = {with_traits}；有攻略 = {with_pets}；含地狱 = {hard}")
print("写出", f"{HERE}/factors-final.json")