# -*- coding: utf-8 -*-
"""把 seer-rebuild 只读 dump 解析并灌入玩家缓存（player_pet_individuals）。

优先读 player/dump/full.json（read_main_full.py 的一次性全量：背包43706＋精英仓库2361＋普通仓库2303）。
若 full.json 不存在，回退 bag.txt / warehouse.txt。

按米米号全量重灌（幂等）；同 catch_time 的跨仓重复由主键 (mimi, species_id, catch_time) 自动去重。
每条携带物种名 name（来自 dump 的本地名称反查）。

运行：python player/load_dump.py [米米号]
"""
import os
import re
import json
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import player_cache as PC  # noqa: E402

DUMP = os.path.join(HERE, "dump")
DEFAULT_MIMI = "753949294"


def _read_text(path):
    """自适配 UTF-8 / UTF-8-BOM / UTF-16（PowerShell 重定向常写 UTF-16）。"""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def parse_bag(path):
    """背包 bag.txt：每行『名称（species=3524 catch_time=1784269070）』 → (sp, ct, name)。"""
    txt = _read_text(path)
    out = []
    for nm, sp, ct in re.findall(r"([^\s（]+)（species=(\d+)\s+catch_time=(\d+)）", txt):
        out.append((sp, ct, nm.strip()))
    return out


def parse_warehouse(path):
    """精英仓库 warehouse.txt：JSON pets 数组 → (sp, ct, name)。"""
    data = json.loads(_read_text(path))
    return [(str(p["species_id"]), str(p["catch_time"]), str(p.get("name") or ""))
            for p in data.get("pets", [])]


def parse_full(path):
    """full.json: {bag/elite/normal: [{species_id, catch_time, name}]} → (sp, ct, name) 去重。"""
    data = json.loads(_read_text(path))
    rows, seen, src = [], set(), {}
    for key in ("bag", "elite", "normal"):
        arr = data.get(key, [])
        src[key] = len(arr)
        for e in arr:
            k = (str(e["species_id"]), str(e["catch_time"]))
            if k not in seen:
                seen.add(k)
                rows.append((k[0], k[1], str(e.get("name") or "")))
    return rows, src


def _clean_names():
    """scrape/pets-index.json（SeerAPI 全量宠物表）→ {seerapiId: clean_name}。"""
    with open(os.path.join(HERE, "..", "scrape", "pets-index.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {str(e["id"]): str(e["name"]) for e in data if e.get("id") is not None}


def parse_roster(path):
    """roster.jsonl（统一契约）→ (sp, ct, name) 去重；name 来自 SeerAPI 全量表。"""
    names = _clean_names()
    rows, seen, src = [], set(), {"bag": 0, "elite": 0, "normal": 0}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("kind") != "pet":
                continue
            sp, ct = str(e["species_id"]), str(e["catch_time"])
            loc = e.get("location", "")
            src[loc] = src.get(loc, 0) + 1
            if (sp, ct) in seen:
                continue
            seen.add((sp, ct))
            rows.append((sp, ct, names.get(sp, "")))
    return rows, src


def main():
    mimi = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MIMI
    roster_path = os.path.join(DUMP, "roster.jsonl")
    full_path = os.path.join(DUMP, "full.json")

    rows, src, mode = [], {}, "fallback(bag+warehouse)"
    if os.path.exists(roster_path):
        rows, src = parse_roster(roster_path)
        mode = "roster.jsonl(统一契约, name=SeerAPI 全量表)"
    elif os.path.exists(full_path):
        rows, src = parse_full(full_path)
        mode = "full.json(旧格式)"
    else:
        seen = set()
        bag_path = os.path.join(DUMP, "bag.txt")
        wh_path = os.path.join(DUMP, "warehouse.txt")
        if os.path.exists(bag_path):
            b = parse_bag(bag_path)
            src["bag(43706)"] = len(b)
            for r in b:
                if (r[0], r[1]) not in seen:
                    seen.add((r[0], r[1]))
                    rows.append(r)
        if os.path.exists(wh_path):
            w = parse_warehouse(wh_path)
            src["warehouse(2361)"] = len(w)
            for r in w:
                if (r[0], r[1]) not in seen:
                    seen.add((r[0], r[1]))
                    rows.append(r)

    conn = PC.connect()
    PC.init_db(conn)
    PC.set_pets(conn, mimi, rows)

    print(f"mimi = {mimi}  模式 = {mode}")
    print("来源:", src)
    print(f"去重后个体数 = {len(rows)}")
    print(f"去重后物种数 = {len({r[0] for r in rows})}")
    print(f"带名字的个体 = {sum(1 for r in rows if r[2])}")
    for sp, label in (("3512", "帝皇之御"), ("5000", "圣灵谱尼"), ("3022", "王之哈莫")):
        print(f"  has_species({label}) = {PC.has_species(conn, mimi, sp)}  "
              f"只数 = {PC.count_species(conn, mimi, sp)}  "
              f"按名命中 = {PC.has_species_by_name(conn, mimi, label)}"
              f"({PC.count_species_by_name(conn, mimi, label)})")
    probs = PC.validate(conn)
    print(f"validate problems = {len(probs)}")
    for p in probs[:10]:
        print("  ", p)
    conn.close()


if __name__ == "__main__":
    main()