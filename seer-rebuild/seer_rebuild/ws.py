"""最小 RFC6455 WebSocket 客户端（asyncio，无第三方依赖）。

2.0.9 的 H5/Unity 链路使用 ``wss://``，协议头为 ``taomee`` /
``h5_web_taomee``（镜像 RVA 0x8c6363 起）。官方客户端由 websocketpp 驱动，
这里只实现本项目需要的二进制帧、ping/pong、close 与分片。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import ssl
import struct
from dataclasses import dataclass
from urllib.parse import urlsplit

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _parse_proxy(proxy: str) -> tuple[str, int]:
    s = proxy
    if "://" in s:
        s = s.split("://", 1)[1]
    host, _, port = s.rpartition(":")
    if not host or not port:
        raise WebSocketError(f"bad proxy: {proxy!r}")
    return host, int(port)


class WebSocketError(RuntimeError):
    pass


@dataclass(slots=True)
class WSConfig:
    origin: str = "https://seerh5.61.com"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    )
    protocols: tuple[str, ...] = ("taomee", "h5_web_taomee")
    extra_headers: dict[str, str] | None = None
    verify_tls: bool = True
    proxy: str | None = None
    open_timeout: float = 15.0


class WebSocket:
    def __init__(self, url: str, cfg: WSConfig | None = None):
        self.url = url
        self.cfg = cfg or WSConfig()
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._recv_buf = bytearray()
        self._frag_opcode: int | None = None
        self._frag_data = bytearray()
        self.closed = False

    async def connect(self) -> None:
        u = urlsplit(self.url)
        if u.scheme not in ("ws", "wss"):
            raise WebSocketError(f"unsupported scheme: {u.scheme}")
        host = u.hostname or ""
        port = u.port or (443 if u.scheme == "wss" else 80)
        path = (u.path or "/") + (("?" + u.query) if u.query else "")
        ssl_ctx = None
        if u.scheme == "wss":
            ssl_ctx = ssl.create_default_context()
            if not self.cfg.verify_tls:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
        if self.cfg.proxy:
            phost, pport = _parse_proxy(self.cfg.proxy)
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(phost, pport),
                timeout=self.cfg.open_timeout,
            )
            self.writer.write(
                (f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n").encode("latin1")
            )
            await self.writer.drain()
            resp = await asyncio.wait_for(self.reader.readuntil(b"\r\n\r\n"), timeout=self.cfg.open_timeout)
            if b" 200 " not in resp.split(b"\r\n", 1)[0]:
                raise WebSocketError("proxy CONNECT failed: " + resp.decode("latin1", "replace")[:200])
            if ssl_ctx is not None:
                await self.writer.start_tls(ssl_ctx, server_hostname=host)
        else:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ssl_ctx, server_hostname=host if ssl_ctx else None),
                timeout=self.cfg.open_timeout,
            )
        key = base64.b64encode(os.urandom(16)).decode()
        headers = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            f"Origin: {self.cfg.origin}",
            f"User-Agent: {self.cfg.user_agent}",
            f"Referer: {self.cfg.origin}/",
        ]
        if self.cfg.protocols:
            headers.append("Sec-WebSocket-Protocol: " + ", ".join(self.cfg.protocols))
        for k, v in (self.cfg.extra_headers or {}).items():
            headers.append(f"{k}: {v}")
        self.writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("latin1"))
        await self.writer.drain()

        raw = await asyncio.wait_for(self.reader.readuntil(b"\r\n\r\n"), timeout=self.cfg.open_timeout)
        head = raw.decode("latin1", "replace")
        status = head.split("\r\n", 1)[0]
        if " 101 " not in status and not status.endswith(" 101"):
            raise WebSocketError(f"handshake failed: {status}\n{head[:500]}")
        headers_map = {}
        for line in head.split("\r\n")[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers_map[k.strip().lower()] = v.strip()
        expect = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        if headers_map.get("sec-websocket-accept") != expect:
            raise WebSocketError("bad Sec-WebSocket-Accept")

    async def send(self, data: bytes, *, opcode: int = 0x2) -> None:
        if not self.writer or self.closed:
            raise WebSocketError("not connected")
        self.writer.write(self._frame(data, opcode))
        await self.writer.drain()

    async def recv(self) -> bytes:
        """返回一个完整二进制消息（自动处理 ping/pong 与分片）。"""
        while True:
            frame = await self._read_frame()
            opcode = frame[0] & 0x0F
            payload = frame[1]
            fin = bool(frame[0] & 0x80)
            if opcode == 0x8:  # close
                self.closed = True
                try:
                    self.writer.close()
                except Exception:
                    pass
                raise WebSocketError("closed by peer")
            if opcode == 0x9:  # ping
                await self.send(payload, opcode=0xA)
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode in (0x1, 0x2):
                if fin:
                    return payload
                self._frag_opcode = opcode
                self._frag_data = bytearray(payload)
                continue
            if opcode == 0x0:  # continuation
                if self._frag_opcode is None:
                    raise WebSocketError("unexpected continuation")
                self._frag_data.extend(payload)
                if fin:
                    data = bytes(self._frag_data)
                    self._frag_opcode = None
                    self._frag_data.clear()
                    return data
                continue
            raise WebSocketError(f"unsupported opcode {opcode}")

    async def close(self) -> None:
        if self.writer and not self.closed:
            try:
                self.writer.write(self._frame(b"", 0x8))
                await self.writer.drain()
            except Exception:
                pass
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.closed = True

    def _frame(self, data: bytes, opcode: int) -> bytes:
        b0 = 0x80 | (opcode & 0x0F)
        n = len(data)
        mask = os.urandom(4)
        if n < 126:
            head = struct.pack("!BB", b0, 0x80 | n)
        elif n < 65536:
            head = struct.pack("!BBH", b0, 0x80 | 126, n)
        else:
            head = struct.pack("!BBQ", b0, 0x80 | 127, n)
        masked = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
        return head + mask + masked

    async def _read_frame(self) -> tuple[int, bytes]:
        if not self.reader:
            raise WebSocketError("not connected")
        h = await self.reader.readexactly(2)
        b0, b1 = h[0], h[1]
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack("!H", await self.reader.readexactly(2))[0]
        elif n == 127:
            n = struct.unpack("!Q", await self.reader.readexactly(8))[0]
        if b1 & 0x80:
            mask = await self.reader.readexactly(4)
            raw = bytearray(await self.reader.readexactly(n))
            for i in range(n):
                raw[i] ^= mask[i % 4]
            payload = bytes(raw)
        else:
            payload = await self.reader.readexactly(n)
        return b0, payload