# -*- coding: utf-8 -*-
"""
玩家实例缓存（ABox 易变层）—— SQLite 关系表，只做 O(1) 存在性筛选。

设计定稿（与用户逐条确认）：
  player_pet_individuals(mimi, species_id, catch_time, name, updated_at)
      PRIMARY KEY (mimi, species_id, catch_time)
      # species_id = 筛选核心（判断「有没有某物种」）；catch_time = 去重键（同一只只留一条）
      # name = 物种名（冗余进缓存，供「策略 pets 是名字」直接命中；SSOT 仍在本体 label）
  player_equipment(mimi, equipment_id, updated_at)   PK (mimi, equipment_id)
  player_titles(mimi, title_id, updated_at)          PK (mimi, title_id)

id 桥（对齐本体命名空间，不复制数据）：
  物种   species_id   -> seer:pet_<id>           （本体已有 seer:Pet 个体 + seer:seerapiId）
  个体   catch_time   -> seer:pet-ind-<catch_time>（占位 IRI，暂无 OWL 类）
  装备   equipment_id -> seer:equipment_<id>      （占位 IRI，暂无 OWL 类）
  称号   title_id     -> seer:title_<id>          （占位 IRI，暂无 OWL 类）

只存「易变集合成员 + 物种名」；其余静态事实（属性/克制/种族值）一律回本体拿，不复制。
刷新源：seer-rebuild 只读 dump（bag/warehouse/2303），经 set_pets 全量重灌。

零第三方依赖，仅用标准库 sqlite3。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone

SEER_NS = "http://example.org/seer#"
DB_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_pet_individuals (
  mimi       TEXT NOT NULL,
  species_id TEXT NOT NULL,
  catch_time TEXT NOT NULL,
  name       TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (mimi, species_id, catch_time)
);
CREATE INDEX IF NOT EXISTS idx_ppi_mimi_name ON player_pet_individuals(mimi, name);
CREATE TABLE IF NOT EXISTS player_equipment (
  mimi         TEXT NOT NULL,
  equipment_id TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  PRIMARY KEY (mimi, equipment_id)
);
CREATE TABLE IF NOT EXISTS player_titles (
  mimi       TEXT NOT NULL,
  title_id   TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (mimi, title_id)
);
"""


# ---------- id 桥 ----------

def pet_iri(species_id) -> str:
    """物种 → 本体 IRI（seer:pet_<id>，本体已有该个体）。"""
    return f"{SEER_NS}pet_{species_id}"


def pet_ind_iri(catch_time) -> str:
    """精灵个体 → 占位 IRI（seer:pet-ind-<catch_time>，暂无 OWL 类）。"""
    return f"{SEER_NS}pet-ind-{catch_time}"


def equipment_iri(equipment_id) -> str:
    """装备 → 占位 IRI（seer:equipment_<id>，暂无 OWL 类）。"""
    return f"{SEER_NS}equipment_{equipment_id}"


def title_iri(title_id) -> str:
    """称号 → 占位 IRI（seer:title_<id>，暂无 OWL 类）。"""
    return f"{SEER_NS}title_{title_id}"


# ---------- 连接 / 建表 ----------

def connect(path: str = DB_DEFAULT) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- 全量重灌（刷新语义：先删该米米号全部，再灌当前 dump） ----------

def set_pets(conn: sqlite3.Connection, mimi, rows) -> None:
    """rows: iterable of (species_id, catch_time[, name])。name 可省略（回退为空）。"""
    conn.execute("DELETE FROM player_pet_individuals WHERE mimi=?", (str(mimi),))
    ts = _now()
    recs = []
    for r in rows:
        if len(r) >= 3:
            s, c, n = r[0], r[1], r[2]
        else:
            s, c, n = r[0], r[1], ""
        recs.append((str(mimi), str(s), str(c), str(n or ""), ts))
    conn.executemany(
        "INSERT INTO player_pet_individuals(mimi, species_id, catch_time, name, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        recs,
    )
    conn.commit()


def set_equipment(conn: sqlite3.Connection, mimi, ids) -> None:
    conn.execute("DELETE FROM player_equipment WHERE mimi=?", (str(mimi),))
    ts = _now()
    conn.executemany(
        "INSERT INTO player_equipment(mimi, equipment_id, updated_at) VALUES (?, ?, ?)",
        [(str(mimi), str(i), ts) for i in ids],
    )
    conn.commit()


def set_titles(conn: sqlite3.Connection, mimi, ids) -> None:
    conn.execute("DELETE FROM player_titles WHERE mimi=?", (str(mimi),))
    ts = _now()
    conn.executemany(
        "INSERT INTO player_titles(mimi, title_id, updated_at) VALUES (?, ?, ?)",
        [(str(mimi), str(i), ts) for i in ids],
    )
    conn.commit()


# ---------- 查询（走主键前缀 / 点查 / (mimi,name) 索引，O(1)） ----------

def has_species(conn: sqlite3.Connection, mimi, species_id) -> bool:
    """玩家是否拥有某物种（至少一只个体）。"""
    row = conn.execute(
        "SELECT 1 FROM player_pet_individuals WHERE mimi=? AND species_id=? LIMIT 1",
        (str(mimi), str(species_id)),
    ).fetchone()
    return row is not None


def count_species(conn: sqlite3.Connection, mimi, species_id) -> int:
    """玩家拥有某物种的个体数量。"""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM player_pet_individuals WHERE mimi=? AND species_id=?",
        (str(mimi), str(species_id)),
    ).fetchone()
    return int(row["n"])


def has_individual(conn: sqlite3.Connection, mimi, species_id, catch_time) -> bool:
    """玩家是否拥有某一只具体个体。"""
    row = conn.execute(
        "SELECT 1 FROM player_pet_individuals "
        "WHERE mimi=? AND species_id=? AND catch_time=? LIMIT 1",
        (str(mimi), str(species_id), str(catch_time)),
    ).fetchone()
    return row is not None


def species_owned(conn: sqlite3.Connection, mimi) -> list:
    """玩家拥有的所有物种 id（去重）。"""
    rows = conn.execute(
        "SELECT DISTINCT species_id FROM player_pet_individuals WHERE mimi=? ORDER BY species_id",
        (str(mimi),),
    ).fetchall()
    return [r["species_id"] for r in rows]


def has_species_by_name(conn: sqlite3.Connection, mimi, name) -> bool:
    """按物种名判断是否拥有（走 (mimi,name) 索引）。"""
    row = conn.execute(
        "SELECT 1 FROM player_pet_individuals WHERE mimi=? AND name=? LIMIT 1",
        (str(mimi), str(name)),
    ).fetchone()
    return row is not None


def count_species_by_name(conn: sqlite3.Connection, mimi, name) -> int:
    """按物种名统计个体数。"""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM player_pet_individuals WHERE mimi=? AND name=?",
        (str(mimi), str(name)),
    ).fetchone()
    return int(row["n"])


def species_id_by_name(conn: sqlite3.Connection, mimi, name):
    """缓存内 名字→species_id（只覆盖玩家拥有的物种；未拥有返回 None）。"""
    row = conn.execute(
        "SELECT DISTINCT species_id FROM player_pet_individuals WHERE mimi=? AND name=? LIMIT 1",
        (str(mimi), str(name)),
    ).fetchone()
    return row["species_id"] if row else None


def has_equipment(conn: sqlite3.Connection, mimi, equipment_id) -> bool:
    row = conn.execute(
        "SELECT 1 FROM player_equipment WHERE mimi=? AND equipment_id=? LIMIT 1",
        (str(mimi), str(equipment_id)),
    ).fetchone()
    return row is not None


def equipment_owned(conn: sqlite3.Connection, mimi) -> list:
    rows = conn.execute(
        "SELECT equipment_id FROM player_equipment WHERE mimi=? ORDER BY equipment_id",
        (str(mimi),),
    ).fetchall()
    return [r["equipment_id"] for r in rows]


def has_title(conn: sqlite3.Connection, mimi, title_id) -> bool:
    row = conn.execute(
        "SELECT 1 FROM player_titles WHERE mimi=? AND title_id=? LIMIT 1",
        (str(mimi), str(title_id)),
    ).fetchone()
    return row is not None


def titles_owned(conn: sqlite3.Connection, mimi) -> list:
    rows = conn.execute(
        "SELECT title_id FROM player_titles WHERE mimi=? ORDER BY title_id",
        (str(mimi),),
    ).fetchall()
    return [r["title_id"] for r in rows]


# ---------- 轻量校验（ABox 版的 merge_check：只拦悬空/空键） ----------

def validate(conn: sqlite3.Connection, known_species_ids=None) -> list:
    """返回问题列表；known_species_ids 为可选的合法物种 id 集合（用于悬空引用检查）。"""
    problems = []
    for r in conn.execute("SELECT mimi, species_id, catch_time FROM player_pet_individuals"):
        if not r["species_id"] or not r["catch_time"]:
            problems.append(f"空键: pet {r['mimi']!r} species={r['species_id']!r} catch={r['catch_time']!r}")
        elif known_species_ids is not None and r["species_id"] not in known_species_ids:
            problems.append(f"悬空引用: {r['mimi']!r} 引用了未知物种 {r['species_id']!r}")
    for r in conn.execute("SELECT mimi, equipment_id FROM player_equipment"):
        if not r["equipment_id"]:
            problems.append(f"空键: equipment {r['mimi']!r}")
    for r in conn.execute("SELECT mimi, title_id FROM player_titles"):
        if not r["title_id"]:
            problems.append(f"空键: title {r['mimi']!r}")
    return problems


# ---------- CLI / 自检 ----------

def _selftest() -> int:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    mimi = "123456789"
    # 同一物种两只个体（不同 catch_time），验证去重 + 计数 + 名字
    set_pets(conn, mimi, [
        ("4618", "t1", "佩洛瑟斯"),
        ("4618", "t2", "佩洛瑟斯"),
        ("4023", "t3", "哀目黑子"),
    ])
    assert has_species(conn, mimi, "4618") is True
    assert has_species(conn, mimi, "4023") is True
    assert has_species(conn, mimi, "9999") is False
    assert count_species(conn, mimi, "4618") == 2
    assert has_individual(conn, mimi, "4618", "t1") is True
    assert has_individual(conn, mimi, "4618", "t9") is False
    # 名字维度
    assert has_species_by_name(conn, mimi, "佩洛瑟斯") is True
    assert count_species_by_name(conn, mimi, "佩洛瑟斯") == 2
    assert species_id_by_name(conn, mimi, "佩洛瑟斯") == "4618"
    assert has_species_by_name(conn, mimi, "不存在") is False

    set_equipment(conn, mimi, ["eq-1", "eq-2"])
    assert has_equipment(conn, mimi, "eq-1") is True
    assert equipment_owned(conn, mimi) == ["eq-1", "eq-2"]

    set_titles(conn, mimi, ["t-吉光凤羽"])
    assert has_title(conn, mimi, "t-吉光凤羽") is True

    # 全量重灌会把已移除的物种淘汰
    set_pets(conn, mimi, [("4023", "t3", "哀目黑子")])
    assert has_species(conn, mimi, "4618") is False
    assert has_species_by_name(conn, mimi, "佩洛瑟斯") is False
    assert count_species(conn, mimi, "4023") == 1

    # 校验：已知物种集里的通过，未知则被拦（此刻表内只剩 4023）
    assert validate(conn, known_species_ids={"4023"}) == []
    assert any("未知物种" in p for p in validate(conn, known_species_ids={"4618"}))

    # id 桥
    assert pet_iri("4618") == "http://example.org/seer#pet_4618"
    assert pet_ind_iri("t1") == "http://example.org/seer#pet-ind-t1"
    assert equipment_iri("eq-1") == "http://example.org/seer#equipment_eq-1"
    assert title_iri("t-x") == "http://example.org/seer#title_t-x"

    print("player_cache selftest OK")
    return 0


def main(argv: list) -> int:
    if "--selftest" in argv:
        return _selftest()
    path = DB_DEFAULT
    if "init" in argv or "validate" in argv:
        rest = [a for a in argv if a not in ("init", "validate")]
        if rest and not rest[0].startswith("-"):
            path = rest[0]
    if "init" in argv:
        conn = connect(path)
        init_db(conn)
        conn.close()
        print(f"init ok -> {path}")
        return 0
    if "validate" in argv:
        conn = connect(path)
        init_db(conn)
        problems = validate(conn)
        for p in problems:
            print("PROBLEM:", p)
        print(f"validate done: {len(problems)} problem(s)")
        conn.close()
        return 0
    print(__doc__)
    print("用法: python player_cache.py init [path] | validate [path] | --selftest")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))