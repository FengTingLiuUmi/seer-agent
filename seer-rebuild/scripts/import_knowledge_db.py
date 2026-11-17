"""JSON -> SQLite 领域知识库 导入脚本。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seer_rebuild.sqlite_kb import build_db, SqliteKB  # noqa: E402


def main() -> None:
    db = build_db()
    kb = SqliteKB(db)
    n_pets = kb.con.execute("SELECT COUNT(*) c FROM pets").fetchone()["c"]
    n_skills = kb.con.execute("SELECT COUNT(*) c FROM skills").fetchone()["c"]
    n_tags = kb.con.execute("SELECT COUNT(*) c FROM tags").fetchone()["c"]
    print(f"建库完成：{db}")
    print(f"pets={n_pets} skills={n_skills} tags={n_tags}")
    kb.close()


if __name__ == "__main__":
    main()