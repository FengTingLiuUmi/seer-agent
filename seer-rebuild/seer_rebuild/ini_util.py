"""GBK INI 解析（支持重复 section，如 .cjc 的多个 [3512]）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class IniDoc:
    sections: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def first(self, name: str) -> dict[str, str] | None:
        for sec, kv in self.sections:
            if sec == name:
                return kv
        return None

    def all(self, name: str) -> list[dict[str, str]]:
        return [kv for sec, kv in self.sections if sec == name]


def _read_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "gbk", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("gbk", "replace")


def parse_ini_text(text: str) -> IniDoc:
    doc = IniDoc()
    cur: dict[str, str] | None = {}
    doc.sections.append(("", cur))
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = {}
            doc.sections.append((line[1:-1].strip(), cur))
            continue
        if cur is None:
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            cur[k.strip()] = v.strip()
    return doc


def load_ini(path: str | Path) -> IniDoc:
    return parse_ini_text(_read_text(path))


def as_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip() in ("真", "1", "true", "True", "yes", "是")


def as_int(v: str | None, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def as_float(v: str | None, default: float = 0.0) -> float:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def as_ids(v: str | None) -> list[int]:
    if not v:
        return []
    out = []
    for part in str(v).replace("，", " ").replace(",", " ").split():
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out