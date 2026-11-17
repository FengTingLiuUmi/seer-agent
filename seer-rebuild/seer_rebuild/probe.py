"""Unity 登录后的只读快照：发送已知只读 cmd，记录响应 body。

这些 cmd 只会查询（日常数值/任务通知/精灵塔/巅峰记录），不修改账号状态。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from .client import GameClient
from .login import LoginSession, authenticate, get_unity_gateway
from .protocol import Frame

READ_ONLY_CMDS = [2707, 8016, 8015, 3452, 3453, 2604, 2002]


@dataclass(slots=True)
class ProbeResult:
    sent: list[int] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"sent": self.sent, "responses": self.responses}


async def run_probe(session: LoginSession, *, keep: float = 8.0) -> ProbeResult:
    c = GameClient(session, mode="unity")
    await c.connect(timeout=20.0)

    result = ProbeResult()
    # 先把连接后已推送到 queue 的帧收下来
    for _ in range(3):
        try:
            f = await asyncio.wait_for(c.frames.get(), timeout=1.0)
            result.responses.append(_frame_dict(f))
        except asyncio.TimeoutError:
            break

    for cmd in READ_ONLY_CMDS:
        result.sent.append(cmd)
        try:
            await c.send(cmd, [])
        except Exception as e:
            result.responses.append({"cmd": cmd, "error": str(e)})
            continue
        end = asyncio.get_running_loop().time() + min(keep, 6.0)
        counted = 0
        while asyncio.get_running_loop().time() < end and counted < 8:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - asyncio.get_running_loop().time()))
            except asyncio.TimeoutError:
                continue
            counted += 1
            result.responses.append(_frame_dict(f))

    await c.close()
    return result


def _frame_dict(f: Frame) -> dict:
    return {"cmd": f.cmd, "result": f.result, "len": len(f.body), "body": f.body.hex()}


async def probe_from_credentials(account: str, password: str) -> dict:
    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    res = await run_probe(sess)
    out = res.as_dict()
    out["uid"] = sess.uid
    return out


def probe_credentials(account: str, password: str) -> dict:
    return asyncio.run(probe_from_credentials(account, password))