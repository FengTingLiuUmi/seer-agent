"""可选 SeerAPI provider：用已安装的 `seerapi` CLI 查询在线游戏数据。

本模块保持零强依赖：默认关闭，查询失败 `graceful=False` 时抛 `SeerApiError`，
否则返回 None。所有结果本地缓存，避免反复起子进程。
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any


class SeerApiError(RuntimeError):
    pass


@dataclass(slots=True)
class SeerApiProvider:
    binary: str = "seerapi"
    scheme: str | None = None
    hostname: str | None = None
    _cache: dict = field(default_factory=dict, init=False, repr=False)

    # ------------------------------------------------------------------
    def _run(self, *args: str) -> Any:
        cmd = [self.binary]
        if self.scheme:
            cmd += ["--scheme", self.scheme]
        if self.hostname:
            cmd += ["--hostname", self.hostname]
        cmd += list(args)
        key = tuple(cmd)
        if key in self._cache:
            return self._cache[key]
        proc = subprocess.run(cmd, capture_output=True)
        out = proc.stdout.decode("utf-8", "replace").strip()
        err = proc.stderr.decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise SeerApiError(err or out or f"exit {proc.returncode}")
        if not out:
            return None
        try:
            value = json.loads(out)
        except json.JSONDecodeError:
            value = out
        self._cache[key] = value
        return value

    # ------------------------------------------------------------------
    def resources(self) -> list[dict]:
        return self._run("resources") or []

    def get(self, resource: str, id_or_name: Any, *, fields: list[str] | None = None) -> dict | None:
        args = ["get", resource, str(id_or_name)]
        if fields:
            args += ["--fields", ",".join(fields)]
        value = self._run(*args)
        return value if isinstance(value, dict) else None

    def get_by_name(self, resource: str, name: str) -> dict | None:
        return self._run("get-by-name", resource, name)

    def find(self, resource: str, name: str, *, limit: int = 5) -> list[dict] | None:
        value = self._run("list", resource, "--name", name, "--limit", str(limit))
        if isinstance(value, dict):
            value = value.get("results") or value.get("items") or value.get("data") or []
        return value if isinstance(value, list) else None

    # ------------------------------------------------------------------
    # 常用领域对象
    def pet(self, id_or_name: Any, *, fields: tuple[str, ...] = ("id", "name", "base_stats", "type", "skill")) -> dict | None:
        return self.get("pet", id_or_name, fields=list(fields))

    def skill(self, id_or_name: Any, *, fields: tuple[str, ...] = ("id", "name", "power", "category", "type")) -> dict | None:
        return self.get("skill", id_or_name, fields=list(fields))

    def item(self, id_or_name: Any, *, fields: tuple[str, ...] = ("id", "name")) -> dict | None:
        return self.get("item", id_or_name, fields=list(fields))

    def error_text(self, code: int) -> str | None:
        try:
            d = self.get("error_code", code, fields=["name"])
            return (d or {}).get("name")
        except SeerApiError:
            return None

    def name(self, resource: str, obj_id: int | str) -> str | None:
        try:
            d = self.get(resource, obj_id, fields=["name"])
            return (d or {}).get("name")
        except SeerApiError:
            return None

    # ------------------------------------------------------------------
    def resolve(self, resource: str, obj_id: Any, fallback: str | None = None) -> str | None:
        """安全反查名称；失败返回 fallback。"""
        try:
            return self.name(resource, obj_id) or fallback
        except Exception:
            return fallback


def build_provider(enabled: bool | str = False, **kwargs: Any) -> SeerApiProvider | None:
    """根据配置创建 provider；`enabled` 为 False/''/'none' 时返回 None。"""
    if not enabled or str(enabled).lower() in ("false", "0", "none", "off", "no"):
        return None
    return SeerApiProvider(**kwargs)