# -*- coding: utf-8 -*-
"""从 SSOT docs 派生 Whoosh 单关索引 kb/index/。
- 索引单元 = 单关（stage），文档字段 mech/template/type 是投影，stage_id 回指 SSOT doc。
- R1 不走这里（直读 docs），R2(机制) / R3(数值模板) 走这里。
幂等重建：每次 docs 更新后重跑本脚本覆盖索引，绝不手改索引。
运行：PYTHONUTF8=1 python build_index.py
"""
import os, json, glob, shutil

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
DOCS = f"{HERE}/docs"
IDX = f"{HERE}/index"

from whoosh import index
from whoosh.fields import Schema, TEXT, ID, NUMERIC, STORED
from whoosh.analysis import SimpleAnalyzer

schema = Schema(
    stage_id=ID(stored=True, unique=True),
    doc_id=TEXT(stored=True),
    factor=TEXT(stored=True),
    difficulty=TEXT(stored=True),
    stage=NUMERIC(stored=True),
    mech=TEXT(stored=True, field_boost=2.0),        # 机制 slug，空格连接
    template=TEXT(stored=True),                      # 数值+属性桶：hp12000 fx300 js16.7 机械地面
    type=TEXT(stored=True),                          # Boss 属性（无·写法）
    apex=STORED(),
)

if os.path.exists(IDX):
    shutil.rmtree(IDX)
os.makedirs(IDX)
ix = index.create_in(IDX, schema)
w = ix.writer()

n = 0
for fp in sorted(glob.glob(f"{DOCS}/*/*.json")):
    if fp.endswith("catalog.json"):
        continue
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)
    for s in d.get("stages", []):
        sid = f"{d['factor']}#{d['difficulty']}#{s['stage']}"
        mech = " ".join(s.get("mech") or [])
        bt = (s.get("boss_type") or "").replace("·", "").replace(" ", "")
        hp = s.get("boss_hp")
        # 数值桶：从 traits 抽 固伤/减伤 值（写死解析，与 mechanisms 解耦）
        fx, js = None, None
        tr = s.get("traits") or ""
        import re
        mfx = re.search(r"(\d+)\s*固伤", tr)
        mjs = re.search(r"减伤\s*([\d.]+)\s*%", tr)
        fx = int(mfx.group(1)) if mfx else None
        js = mjs.group(1) if mjs else None
        templ_tokens = [bt] if bt else []
        if hp is not None:
            templ_tokens.append(f"hp{hp}")
        if fx is not None:
            templ_tokens.append(f"fx{fx}")
        if js is not None:
            templ_tokens.append(f"js{js}")
        if not templ_tokens:
            templ_tokens = ["na"]
        w.add_document(
            stage_id=sid,
            doc_id=d["doc_id"],
            factor=d["factor"],
            difficulty=d["difficulty"],
            stage=s["stage"],
            mech=mech,
            template=" ".join(templ_tokens),
            type=bt or "na",
            apex="1" if s.get("apex") else "0",
        )
        n += 1
w.commit()
print(f"indexed {n} stages -> {IDX}")
print("fields:", ix.schema.names())