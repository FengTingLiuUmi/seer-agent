"""赛尔号 PVE 知识库（llmwiki）检索层。

一页一主题的 markdown + YAML frontmatter + ``[[backlink]]`` 关联。
父 agent 组队的「读 BOSS → 组队」入口：

    from seer_rebuild import wiki
    wiki.boss(4092)                # {'meta': {...}, 'body': '...'}
    wiki.find(tag='boss', type='光')
    wiki.search('弹伤')
    wiki.backlinks('八四公式')

不依赖 PyYAML：frontmatter 只解析极简子集（``key: 标量`` 与
``type/tags/aliases`` 这类逗号列表字段）。
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "llmwiki"

# 逗号分隔的列表字段（其余按标量解析）
LIST_KEYS = {"type", "tags", "aliases"}

# backlink 语法 [[目标名]]
_BACKLINK = re.compile(r"\[\[([^\]]+)\]\]")


def _scalar(v: str):
    v = v.strip()
    if v == "":
        return None
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if v.lstrip("-").isdigit():
        return int(v)
    return v


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """返回 (meta, body)。meta 不含 name 以外的废话。"""
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    meta: dict = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or ":" not in line or line.startswith("#"):
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if k in LIST_KEYS:
            meta[k] = [_scalar(x) for x in v.split(",") if x.strip() != ""]
        else:
            meta[k] = _scalar(v)
    return meta, parts[2].strip()


def iter_pages():
    """遍历 llmwiki/ 下所有 .md，yield (相对路径, meta, body)。"""
    for p in sorted(BASE.rglob("*.md")):
        raw = p.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        yield p.relative_to(BASE).as_posix(), meta, body


def _norm_path(rel: str) -> str:
    rel = rel.replace("\\", "/").strip()
    rel = rel[2:] if rel.startswith("./") else rel
    return rel.strip("/")


def _is_meta_page(rel: str) -> bool:
    """模板/目录等非知识点页（文件名以 _ 开头）。"""
    return Path(rel).name.startswith("_")


def read_page(rel: str) -> dict | None:
    """按相对路径读一页。"""
    rel = _norm_path(rel)
    target = BASE / rel
    if not target.is_file():
        return None
    raw = target.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)
    return {"path": target.relative_to(BASE).as_posix(), "meta": meta, "body": body}


def boss(species: int) -> dict | None:
    """按 species 读 BOSS 页（只在 bosses/ 下找）。"""
    for rel, meta, body in iter_pages():
        if _is_meta_page(rel):
            continue
        if not rel.startswith("bosses/"):
            continue
        if meta.get("species") == species:
            return {"path": rel, "meta": meta, "body": body}
    return None


def list_pages(category: str | None = None) -> list[dict]:
    """列全部页面（可按一级目录过滤）。"""
    out = []
    for rel, meta, _body in iter_pages():
        if _is_meta_page(rel):
            continue
        if category and not rel.startswith(category.rstrip("/") + "/"):
            continue
        out.append({"path": rel, "name": meta.get("name"), "species": meta.get("species"),
                    "type": meta.get("type"), "tags": meta.get("tags")})
    return out


def categories() -> dict[str, int]:
    d: dict[str, int] = {}
    for rel, _meta, _body in iter_pages():
        top = rel.split("/", 1)[0]
        d[top] = d.get(top, 0) + 1
    return d


def find(*, tag: str | None = None, type_: str | None = None,
         species: int | None = None, name: str | None = None,
         keyword: str | None = None, category: str | None = None) -> list[dict]:
    """frontmatter 过滤 + 关键词。全部条件 AND。"""
    out = []
    for rel, meta, body in iter_pages():
        if _is_meta_page(rel):
            continue
        if category and not rel.startswith(category.rstrip("/") + "/"):
            continue
        if tag and tag not in (meta.get("tags") or []):
            continue
        if type_ is not None and type_ not in (meta.get("type") or []):
            continue
        if species is not None and meta.get("species") != species:
            continue
        if name and name not in (meta.get("name") or ""):
            continue
        if keyword:
            blob = (str(meta.get("name") or "") + " " + ",".join(map(str, meta.get("aliases") or []))
                    + "\n" + body).lower()
            if keyword.lower() not in blob:
                continue
        out.append({"path": rel, "meta": meta, "body": body})
    return out


def search(keyword: str, *, limit: int = 20) -> list[dict]:
    """全文关键词检索，返回命中页 + 摘要。"""
    out = []
    kw = keyword.lower()
    for rel, meta, body in iter_pages():
        if _is_meta_page(rel):
            continue
        blob = (str(meta.get("name") or "") + " " + ",".join(map(str, meta.get("aliases") or []))
                + "\n" + body)
        low = blob.lower()
        idx = low.find(kw)
        if idx == -1:
            continue
        start = max(0, idx - 40)
        snippet = blob[start:idx + len(kw) + 60].replace("\n", " ")
        out.append({"path": rel, "name": meta.get("name"), "snippet": snippet})
        if len(out) >= limit:
            break
    return out


def backlinks(name: str) -> list[str]:
    """找出正文里 ``[[name]]`` 引用了它的页面。"""
    hits = []
    needle = f"[[{name}]]"
    for rel, _meta, body in iter_pages():
        if needle in body:
            hits.append(rel)
    return hits


def backlinks_of_page(rel: str) -> list[str]:
    """取某一页正文里的 backlink 目标。"""
    page = read_page(rel)
    if not page:
        return []
    return sorted({m for m in _BACKLINK.findall(page["body"])})