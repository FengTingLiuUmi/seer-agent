"""游戏客户端：H5/Unity WSS 与 Flash TCP 两条链路。"""
from __future__ import annotations

import asyncio
import ssl
import struct
from collections.abc import Callable
from typing import Any

from .login import LoginSession, build_flash_login, build_h5_login_body, build_unity_login_body, get_unity_gateway, parse_gateway
from .protocol import Frame, FrameSplitter, FlashEncoder, H5Encoder, pack_h5
from .ws import WSConfig, WebSocket, WebSocketError


class GameClient:
    def __init__(
        self,
        session: LoginSession,
        *,
        mode: str = "unity",
        area_id: int | None = None,
        platform: str = "unity_app_taomee",
        version: int = 0x31,
        proxy: str | None = None,
        logger: Callable[[str], None] | None = None,
    ):
        if mode not in ("unity", "flash", "h5"):
            raise ValueError("mode must be unity/flash/h5")
        self.session = session
        self.mode = mode
        self.area_id = area_id
        self.platform = platform
        self.version = version & 0xFF
        self.proxy = proxy
        self.log = logger or (lambda s: None)
        self.ws: WebSocket | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.encoder = H5Encoder(session.uid, version=self.version) if mode in ("unity", "h5") else FlashEncoder(session.uid)
        self.splitter = FrameSplitter(mode="h5" if mode in ("unity", "h5") else "flash")
        self.frames: asyncio.Queue[Frame] = asyncio.Queue()
        self._pending: dict[int, list[asyncio.Future]] = {}
        self._reader_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self.connected = False

    # ------------------------------------------------------------------ H5
    async def connect(self, *, timeout: float = 15.0) -> Frame | None:
        if self.mode == "unity":
            return await self._connect_unity_tcp(timeout=timeout)
        if self.mode == "h5":
            return await self._connect_h5(timeout=timeout)
        return await self._connect_flash(timeout=timeout)

    async def _connect_h5(self, *, timeout: float) -> Frame | None:
        if not self.session.host:
            if not self.session.gateway:
                raise ValueError("session has no gateway")
            host, port, path = parse_gateway(self.session.gateway)
            self.session.host, self.session.port, self.session.path = host, port, path
        url = f"wss://{self.session.host}:{self.session.port}{self.session.path or '/'}"
        self.log(f"[ws] connecting {url}")
        cfg = WSConfig(
            origin="https://seerh5.61.com",
            protocols=("taomee", "h5_web_taomee") if self.mode == "unity" else ("taomee",),
            proxy=self.proxy,
        )
        self.ws = WebSocket(url, cfg)
        await self.ws.connect()
        self.connected = True
        self._reader_task = asyncio.create_task(self._read_loop_ws())
        if self.mode == "unity":
            body = build_h5_login_body(
                self.session, area_id=self.area_id, platform=self.platform
            )
        else:
            body = build_flash_login(self.session)
        self.log(f"[login] send 1001 body={len(body)}B")
        await self.send(1001, [body])
        try:
            first = await asyncio.wait_for(self._wait_cmd(1001), timeout=timeout)
            self.log(f"[login] got 1001 result={first.result} body={first.body[:32].hex()}")
            return first
        except asyncio.TimeoutError:
            self.log("[login] 1001 timeout (server may require area/session correction)")
            return None

    async def _read_loop_ws(self) -> None:
        assert self.ws
        try:
            while True:
                data = await self.ws.recv()
                self._feed(data)
        except (WebSocketError, asyncio.IncompleteReadError, ConnectionError) as e:
            self.log(f"[ws] closed: {e}")
        finally:
            self.connected = False

    # --------------------------------------------------------------- Unity
    async def _connect_unity_tcp(self, *, timeout: float) -> Frame | None:
        # 2.0.9 FUN_0044b723：随机 IP + 随机端口(1202..1230)，最多重试 6 次。
        last_err: Exception | None = None
        for attempt in range(1, 7):
            host, port = get_unity_gateway()
            self.session.host, self.session.port, self.session.path = host, port, "/"
            self.log(f"[unity] connecting tcp://{host}:{port} (try {attempt}/6)")
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout,
                )
                last_err = None
                break
            except Exception as e:  # noqa: BLE001 - 重试下一个随机端口
                last_err = e
                self.log(f"[unity] connect failed: {e}")
                self.reader = self.writer = None
        if last_err is not None or self.writer is None:
            self.log(f"[unity] give up connecting: {last_err}")
            return None
        self.connected = True
        self._reader_task = asyncio.create_task(self._read_loop_tcp())
        body = build_unity_login_body(self.session, area_id=self.area_id or 1, platform=self.platform)
        self.log(f"[login] send 1001 body={len(body)}B")
        await self.send(1001, [body])

        loop = asyncio.get_running_loop()

        # 1) 先等 S2C 1001 登录快照（_feed 已把它的非 0 result 并入校验链），再发引导帧。
        first_1001: Frame | None = None
        end = loop.time() + timeout
        while first_1001 is None and loop.time() < end:
            try:
                f = await asyncio.wait_for(self.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == 1001:
                first_1001 = f
                self.log(f"[unity] got S2C 1001 result={f.result}")
                break

        # 2) 引导帧（petbag_ws / seer-proto 实测顺序）：42494 + 1002(心跳) + 1016(GET_SESSION_KEY, body=u32(2))
        await self.send(42494, [])
        await self.send(1002, [])
        await self.send(1016, [struct.pack(">I", 2)])

        # 3) 会话握手：token 来自 S2C 2002(len>=4) / 1002(len>=4) / 2001(ENTER_MAP, body[4:8])，
        #    在 45963 回传 `[2][1][token]`（否则服务端不推背包/业务数据）。
        token: bytes | None = None
        end = loop.time() + timeout
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(self.frames.get(), timeout=min(1.0, end - loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == 2002 and len(f.body) >= 4:
                token = f.body[:4]
            elif f.cmd == 1002 and len(f.body) >= 4:
                token = f.body[:4]
            elif f.cmd == 2001 and len(f.body) >= 8:
                token = f.body[4:8]
            if token:
                self.log(f"[unity] got token {token.hex()} via cmd={f.cmd}")
                break

        if token:
            self.token = token
            try:
                await self.send(45963, [struct.pack(">I", 2) + struct.pack(">I", 1) + token])
                self.log("[unity] echo token via 45963")
            except (ConnectionError, asyncio.IncompleteReadError):
                pass
        else:
            self.token = b"\x00\x00\x00\x00"

        return first_1001

    # --------------------------------------------------------------- Flash
    async def _connect_flash(self, *, timeout: float) -> Frame | None:
        if not self.session.host:
            if not self.session.gateway:
                raise ValueError("session has no gateway")
            host, port, path = parse_gateway(self.session.gateway)
            self.session.host, self.session.port, self.session.path = host, port, path
        host, port = self.session.host, self.session.port or 3007
        self.log(f"[tcp] connecting {host}:{port}")
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl.create_default_context() if self.session.mode == "flash_tls" else None),
            timeout=timeout,
        )
        self.connected = True
        self._reader_task = asyncio.create_task(self._read_loop_tcp())
        frame = build_flash_login(self.session)
        self.writer.write(frame)
        await self.writer.drain()
        self.log(f"[login] send flash 1001 frame={frame.hex()}")
        try:
            return await asyncio.wait_for(self._wait_cmd(1001), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def _read_loop_tcp(self) -> None:
        assert self.reader
        try:
            while True:
                chunk = await self.reader.read(65536)
                if not chunk:
                    break
                self._feed(chunk)
        except (asyncio.IncompleteReadError, ConnectionError) as e:
            self.log(f"[tcp] closed: {e}")
        finally:
            self.connected = False

    # ------------------------------------------------------------- common
    def _feed(self, data: bytes) -> None:
        for f in self.splitter.push(data):
            # 关键：result 链要把「服务端下行帧的非 0 result」也算进累积器，
            # 否则下一个 C2S 帧的校验和会错（seer-proto 进展5；这也是在线读不到背包的真因）。
            if f.result != 0:
                self.encoder.result = f.result
            self.frames.put_nowait(f)
            self.log(
                f"[recv] cmd={f.cmd} uid={f.uid} result={f.result} len={len(f.body)} "
                f"body={f.body[:24].hex()}"
            )
            waiters = self._pending.pop(f.cmd, [])
            for fut in waiters:
                if not fut.done():
                    fut.set_result(f)

    async def _wait_cmd(self, cmd: int) -> Frame:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending.setdefault(cmd, []).append(fut)
        return await fut

    async def send(self, cmd: int, args: list[Any] | None = None) -> bytes:
        frame = self.encoder.pack(cmd, args)
        if self.ws:
            await self.ws.send(frame)
        elif self.writer:
            self.writer.write(frame)
            await self.writer.drain()
        else:
            raise RuntimeError("not connected")
        self.log(f"[send] cmd={cmd} len={len(frame)} hex={frame[:48].hex()}")
        return frame

    async def request(self, cmd: int, args: list[Any] | None = None, *, timeout: float = 10.0) -> Frame:
        fut = asyncio.create_task(self._wait_cmd(cmd))
        await asyncio.sleep(0)
        await self.send(cmd, args)
        return await asyncio.wait_for(fut, timeout=timeout)

    async def next_frame(self, timeout: float = 10.0) -> Frame:
        return await asyncio.wait_for(self.frames.get(), timeout=timeout)

    def start_heartbeat(self, cmd: int = 101, interval: float = 20.0) -> None:
        async def loop() -> None:
            while self.connected:
                try:
                    await self.send(cmd, [])
                except Exception as e:
                    self.log(f"[heartbeat] {e}")
                    break
                await asyncio.sleep(interval)

        self._heartbeat_task = asyncio.create_task(loop())

    async def close(self) -> None:
        self.connected = False
        for t in (self._heartbeat_task, self._reader_task):
            if t:
                t.cancel()
        if self.ws:
            await self.ws.close()
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass