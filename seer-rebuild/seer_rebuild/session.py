"""登录会话基础：一次鉴权、可复用连接，供后续功能（装备/背包/因子/战斗）拆分调用。

用法：
    sess = GameSession(account, password)
    info = sess.login()              # 鉴权 + Unity 建连发 1001，返回登录信息
    snap = sess.snapshot(resolve=True)  # 复用鉴权缓存读装备/装扮/称号
    frame = sess.send(cmd, args)     # 复用连接发一条命令收响应
    sess.close()

说明：
  - 鉴权结果缓存在进程内（`authenticate_cached`），重复读取不再走 account-co。
  - 赛尔号 Unity 连接空闲会断，所以每次操作各自建连；会话价值在「鉴权复用 +
    统一连接模板 + 清晰 API」，后续功能都在此基础之上拆。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .client import GameClient
from .inventory import InventorySnapshot, resolve, snapshot_from_live
from .connection import new_login
from .login import LoginSession
from .protocol import Frame


@dataclass(slots=True)
class LoginInfo:
    uid: int
    host: str
    port: int
    result: int | None
    body_hex: str
    masked_session: str


@dataclass(slots=True)
class GameSession:
    account: str
    password: str
    _login: LoginSession | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    def _new_login(self) -> LoginSession:
        self._login = new_login(self.account, self.password)
        return self._login

    def _client(self) -> GameClient:
        sess = self._login if self._login else self._new_login()
        return GameClient(sess, mode="unity")

    # ------------------------------------------------------------------
    def login(self, *, keep: float = 4.0) -> LoginInfo:
        """鉴权 + Unity 建连发 1001，返回登录信息与收到的关键帧。"""
        async def _run() -> LoginInfo:
            sess = self._new_login()
            c = GameClient(sess, mode="unity")
            await c.connect(timeout=20.0)
            result = None
            body = b""
            loop = asyncio.get_running_loop()
            end = loop.time() + keep
            while loop.time() < end:
                try:
                    f = await asyncio.wait_for(
                        c.frames.get(), timeout=min(1.0, end - loop.time())
                    )
                except asyncio.TimeoutError:
                    continue
                if f.cmd == 1001:
                    result = f.result
                    body = f.body
            await c.close()
            return LoginInfo(
                uid=sess.uid,
                host=sess.host or "",
                port=sess.port or 0,
                result=result,
                body_hex=body.hex(),
                masked_session=(sess.session[:6] + "..." + sess.session[-4:]) if sess.session else "",
            )

        return asyncio.run(_run())

    def snapshot(self, *, resolve_names: bool = True) -> InventorySnapshot:
        """读当前装备/装扮/称号（复用鉴权缓存）。"""
        snap = snapshot_from_live(self.account, self.password, None)
        if resolve_names:
            from .provider import SeerApiProvider
            snap = resolve(snap, SeerApiProvider())
        return snap

    def send(self, cmd: int, args: list[Any] | None = None, *, wait: float = 3.0) -> list[Frame]:
        """复用登录连接，发一条命令并收集响应帧。"""
        async def _run() -> list[Frame]:
            c = self._client()
            await c.connect(timeout=20.0)
            await c.send(cmd, args or [])
            out: list[Frame] = []
            loop = asyncio.get_running_loop()
            end = loop.time() + wait
            while loop.time() < end:
                try:
                    f = await asyncio.wait_for(
                        c.frames.get(), timeout=min(1.0, end - loop.time())
                    )
                except asyncio.TimeoutError:
                    continue
                out.append(f)
            await c.close()
            return out

        return asyncio.run(_run())

    def close(self) -> None:
        self._login = None