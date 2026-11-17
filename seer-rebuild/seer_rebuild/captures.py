"""分析官方 H5 抓包（seer-auto 的 SEERWS / frames.jsonl）。

这些抓包不是 2.0.9 主程序，但能用来校准协议帧与 1001 登录 body。
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CaptureFrame:
    cmd: int
    uid: int | None
    body: bytes
    direction: str = ""
    t: int | None = None


@dataclass(slots=True)
class CaptureSummary:
    frames: int = 0
    commands: dict[int, int] = field(default_factory=dict)
    login_body: bytes | None = None
    login_uid: int | None = None

    def as_dict(self) -> dict:
        return {
            "frames": self.frames,
            "commands": dict(sorted(self.commands.items(), key=lambda kv: -kv[1])),
            "login_uid": self.login_uid,
            "login_body_hex": self.login_body.hex() if self.login_body else None,
            "login_body_len": len(self.login_body) if self.login_body else 0,
        }


def iter_capture(path: str | Path) -> list[CaptureFrame]:
    out: list[CaptureFrame] = []
    for raw in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        d = None
        if line.startswith("SEERWS "):
            try:
                d = json.loads(line[7:])
            except json.JSONDecodeError:
                continue
        elif line.startswith("{"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
        if not d:
            continue
        cmd = d.get("cmd")
        if cmd is None:
            continue
        body_hex = d.get("bodyHex")
        if body_hex:
            body = bytes.fromhex(body_hex)
        elif d.get("b64"):
            body = base64.b64decode(d["b64"])
        else:
            body = b""
        out.append(CaptureFrame(int(cmd), d.get("uid"), body, d.get("kind", ""), d.get("t")))
    return out


def summarize(path: str | Path) -> CaptureSummary:
    s = CaptureSummary()
    for f in iter_capture(path):
        s.frames += 1
        s.commands[f.cmd] = s.commands.get(f.cmd, 0) + 1
        if f.cmd == 1001 and s.login_body is None:
            s.login_body = f.body
            s.login_uid = f.uid
    return s


def compact_1001_body(session: bytes, server_id: int, *, size: int = 79) -> bytes:
    """抓包中官方 H5 的 1001 body：16B session + u16 serverid + 0 填充。"""
    b = bytearray(size)
    b[0:16] = (session + b"\x00" * 16)[:16]
    b[0x10:0x12] = int(server_id).to_bytes(2, "big")
    return bytes(b)