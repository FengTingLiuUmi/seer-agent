"""SQLite 领域知识库：建库(JSON→SQLite) + 查询层。零第三方依赖（标准库 sqlite3）。

数据源：seer_rebuild/domain_knowledge/{tags,skills,pets}.json
DB 文件：seer_rebuild/domain_knowledge/knowledge.db
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parent / "domain_knowledge"
DB_PATH = BASE / "knowledge.db"

UPPER_TAGS = {"pve", "pvp"}
ROLE_TAGS = {"站场", "补刀", "强攻", "辅助", "弹伤"}


def _layer(tag: str) -> str:
    if tag in UPPER_TAGS:
        return "上层"
    if tag in ROLE_TAGS:
        return "定位"
    return "机制"


def build_db(db_path: str | Path | None = None, *, json_dir: str | Path | None = None) -> Path:
    """从 JSON 建库。返回 db 路径。"""
    db_path = Path(db_path) if db_path else DB_PATH
    json_dir = Path(json_dir) if json_dir else BASE
    db_path.parent.mkdir(parents=True, exist_ok=True)

    tags = json.load(open(json_dir / "tags.json", encoding="utf-8"))
    skills = json.load(open(json_dir / "skills.json", encoding="utf-8"))
    pets = json.load(open(json_dir / "pets.json", encoding="utf-8"))

    con = sqlite3.connect(db_path)
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))

    # tags（先补全：把技能/精灵/魂印里用到的所有标签也纳入，避免 FK 失败）
    all_tags: set[str] = set(tags.keys())
    for s in skills.values():
        all_tags.update(s.get("tags", []))
    for p in pets.values():
        all_tags.update(p.get("role_tags") or [])
        all_tags.update(p.get("soulmark_tags") or [])
    con.executemany("INSERT OR IGNORE INTO tags(tag, meaning, layer) VALUES(?,?,?)",
                    [(t, tags.get(t, "自动识别标签"), _layer(t)) for t in all_tags])

    # skills + skill_tags
    for sid, s in skills.items():
        con.execute("INSERT INTO skills(skill_id,name,power,cat,type,priority,desc) VALUES(?,?,?,?,?,?,?)",
                    (int(sid), s.get("name", str(sid)), s.get("power", 0), s.get("cat", 0),
                     s.get("type", 0), s.get("priority", 0), s.get("desc", "")))
        for t in s.get("tags", []):
            con.execute("INSERT OR IGNORE INTO skill_tags(skill_id,tag) VALUES(?,?)", (int(sid), t))

    # pets + pet_skills
    for sid, p in pets.items():
        mode = p.get("mode") or "pve"
        con.execute("INSERT INTO pets(species_id,name,type,mode,aliases,role_tags,soulmark_desc,soulmark_tags) VALUES(?,?,?,?,?,?,?,?)",
                    (int(sid), p.get("name", str(sid)), p.get("type", 0), mode,
                     json.dumps(p.get("aliases") or [], ensure_ascii=False),
                     json.dumps(p.get("role_tags") or [], ensure_ascii=False),
                     p.get("soulmark_desc") or "",
                     json.dumps(p.get("soulmark_tags") or [], ensure_ascii=False)))
        for sk in p.get("skills", []):
            con.execute("INSERT OR IGNORE INTO pet_skills(species_id,skill_id) VALUES(?,?)", (int(sid), int(sk)))

    con.commit()
    con.close()
    return db_path


class SqliteKB:
    def __init__(self, db_path: str | Path | None = None):
        # 文件不存在时自动建库
        self.db_path = Path(db_path) if db_path else DB_PATH
        if not self.db_path.exists():
            build_db(self.db_path)
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row

    def close(self) -> None:
        self.con.close()

    # ---- 基础查询 ----
    def pet(self, species_id: int) -> dict | None:
        r = self.con.execute("SELECT * FROM pets WHERE species_id=?", (species_id,)).fetchone()
        return self._pet_row(r) if r else None

    def skill(self, skill_id: int) -> dict | None:
        r = self.con.execute("SELECT * FROM skills WHERE skill_id=?", (skill_id,)).fetchone()
        return dict(r) if r else None

    def tag_meaning(self, tag: str) -> str:
        r = self.con.execute("SELECT meaning FROM tags WHERE tag=?", (tag,)).fetchone()
        return r["meaning"] if r else ""

    def find_alias(self, alias: str) -> dict | None:
        r = self.con.execute(
            "SELECT * FROM pets WHERE EXISTS (SELECT 1 FROM json_each(pets.aliases) WHERE value=?)",
            (alias,),
        ).fetchone()
        return self._pet_row(r) if r else None

    def _pet_row(self, r: sqlite3.Row) -> dict:
        d = dict(r)
        d["aliases"] = json.loads(d["aliases"] or "[]")
        d["role_tags"] = json.loads(d["role_tags"] or "[]")
        d["soulmark_tags"] = json.loads(d["soulmark_tags"] or "[]")
        return d

    # ---- 标签能力 ----
    def skill_tags(self, skill_id: int) -> set[str]:
        rows = self.con.execute("SELECT tag FROM skill_tags WHERE skill_id=?", (skill_id,)).fetchall()
        return {r["tag"] for r in rows}

    def pet_tags(self, species_id: int) -> set[str]:
        """精灵全部标签 = 定位 + 魂印 + 所有实战技能标签。"""
        p = self.pet(species_id)
        if not p:
            return set()
        out = set(p["role_tags"]) | set(p["soulmark_tags"])
        rows = self.con.execute(
            "SELECT skt.tag FROM pet_skills psk JOIN skill_tags skt ON skt.skill_id=psk.skill_id WHERE psk.species_id=?",
            (species_id,),
        ).fetchall()
        out |= {r["tag"] for r in rows}
        return out

    def pets_with_tags(self, tags: list[str], *, require_all: bool = True) -> list[dict]:
        want = set(tags)
        out = []
        for row in self.con.execute("SELECT species_id FROM pets").fetchall():
            got = self.pet_tags(row["species_id"])
            ok = want <= got if require_all else bool(want & got)
            if ok:
                out.append(self.pet(row["species_id"]))
        return out

    def missing_tags(self, species_id: int, tags: list[str]) -> list[str]:
        got = self.pet_tags(species_id)
        return [t for t in tags if t not in got]


def query(db_path: str | Path | None = None) -> SqliteKB:
    return SqliteKB(db_path)