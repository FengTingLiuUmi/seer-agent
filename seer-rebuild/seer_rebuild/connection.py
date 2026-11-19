"""统一建连工厂：鉴权 + 网关 + GameClient + connect。

所有功能想开一条 Unity 明文连接，只调这两个，不要各自手写
``authenticate -> get_unity_gateway -> 填 host/port/mode -> GameClient -> connect``。

赛尔号 Unity 连接空闲会断，所以约定是「每次操作各自建连」，会话价值在鉴权复用
（``authenticate_cached`` 30 分钟缓存）。
"""
from __future__ import annotations

from .client import GameClient
from .login import LoginSession, authenticate_cached, get_unity_gateway


def new_login(account: str, password: str) -> LoginSession:
    """鉴权（带缓存）+ 取 Unity 网关，并填好 host/port/path/mode。"""
    sess = authenticate_cached(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    return sess


async def open_unity(account: str, password: str, *, timeout: float = 20.0) -> GameClient:
    """建一条已连接的 Unity 明文客户端（含 1001 握手 + token 回传）。"""
    c = GameClient(new_login(account, password), mode="unity")
    await c.connect(timeout=timeout)
    return c