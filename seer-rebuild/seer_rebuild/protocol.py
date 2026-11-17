"""赛尔号协议帧编解码（H5/Unity 与 Flash 两套头）。

证据（2.0.9 内存镜像，RVA 0x8c6363-0x8c64d9）：
  - ``wss://``、``h5_web_taomee``、``taomee``、``Recv.%02X``
  - ``https://seerh5login.61.com/online_gate?is_ssl=1``
  - 十六进制常量 ``0000001500000065000022B80000000000000000``

两套头都是 17 字节，只差 version：
  H5:    [u32 totalLen][u8 version=0x31/0x3e][u32 cmd][u32 uid][i32 result][body]
  Flash: [u32 totalLen][u8 version=0x00][u32 cmd][u32 uid][i32 result][body]

Flash 常量的 21 字节正好 = 17B 头 + 4B body：
  total=21, version=0, cmd=101, uid=8888, result=0, body=00000000。

H5 的 result 是跨帧累积校验；Flash 的 result/加密仍未确认，这里先按 0 处理。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable, Any

HEAD_LEN = 17
HEAD_LEN_H5 = 17
HEAD_LEN_FLASH = 17
VERSION_H5 = 0x31
VERSION_FLASH = 0x00
PACKAGE_MAX = 0x800000


class ProtocolError(ValueError):
    pass


def serialize_args(args: Iterable[Any] | None) -> bytes:
    """官方客户端的参数序列化：数组递归、字符串 UTF-8 无前缀、整数 u32 BE。"""
    parts: list[bytes] = []
    for a in args or ():
        if a is None:
            continue
        if isinstance(a, (bytes, bytearray, memoryview)):
            parts.append(bytes(a))
        elif isinstance(a, str):
            parts.append(a.encode("utf-8"))
        elif isinstance(a, bool):
            parts.append(struct.pack(">I", int(a)))
        elif isinstance(a, int):
            parts.append(struct.pack(">I", a & 0xFFFFFFFF))
        elif isinstance(a, (list, tuple)):
            parts.append(serialize_args(a))
        else:
            raise TypeError(f"unsupported arg type: {type(a)!r}")
    return b"".join(parts)


def _pack(version: int, cmd: int, body: bytes, uid: int, result: int) -> bytes:
    total = HEAD_LEN + len(body)
    if total > PACKAGE_MAX:
        raise ProtocolError(f"frame too large: {total}")
    return struct.pack(">IBIII", total, version & 0xFF, cmd & 0xFFFFFFFF, uid & 0xFFFFFFFF, result & 0xFFFFFFFF) + bytes(body)


def pack_h5(cmd: int, body: bytes | bytearray = b"", *, uid: int, result: int = 0, version: int = VERSION_H5) -> bytes:
    return _pack(version, cmd, bytes(body), uid, result)


def pack_flash(cmd: int, body: bytes | bytearray = b"", *, uid: int, result: int = 0, version: int = VERSION_FLASH) -> bytes:
    return _pack(version, cmd, bytes(body), uid, result)


@dataclass(slots=True)
class Frame:
    cmd: int
    uid: int
    result: int
    body: bytes
    raw: bytes
    version: int | None = None

    def __repr__(self) -> str:
        return f"Frame(cmd={self.cmd}, uid={self.uid}, result={self.result}, body={self.body[:16].hex()}...)"


def _parse(buf: bytes) -> Frame:
    if len(buf) < HEAD_LEN:
        raise ProtocolError("short frame")
    total, version, cmd, uid, result = struct.unpack_from(">IBIII", buf, 0)
    if total < HEAD_LEN or total > PACKAGE_MAX:
        raise ProtocolError(f"bad frame length {total}")
    if len(buf) < total:
        raise ProtocolError(f"incomplete frame: {len(buf)}/{total}")
    return Frame(cmd, uid, result, buf[HEAD_LEN:total], buf[:total], version)


def parse_h5(buf: bytes) -> Frame:
    # 官方 H5 抓包存在 0x31 与 0x3e 两种 version；不强制单一值。
    return _parse(buf)


def parse_flash(buf: bytes) -> Frame:
    return _parse(buf)


class FrameSplitter:
    """处理 WebSocket/TCP 粘包与半包。"""

    def __init__(self, mode: str = "h5"):
        if mode not in ("h5", "flash"):
            raise ValueError("mode must be h5 or flash")
        self.mode = mode
        self.buf = bytearray()

    def push(self, chunk: bytes) -> list[Frame]:
        self.buf.extend(chunk)
        out: list[Frame] = []
        while len(self.buf) >= 4:
            total = struct.unpack_from(">I", self.buf, 0)[0]
            if total < HEAD_LEN or total > PACKAGE_MAX:
                raise ProtocolError(f"bad frame length {total}")
            if len(self.buf) < total:
                break
            raw = bytes(self.buf[:total])
            del self.buf[:total]
            out.append(parse_h5(raw) if self.mode == "h5" else parse_flash(raw))
        return out


def result_formula(prev_result: int, cmd: int, body: bytes) -> int:
    """官方 H5 ``packHead`` 的跨帧校验（不是加密）。"""
    if cmd <= 1000:
        return 0
    s = 0
    for byte in body:
        s ^= byte
    value = prev_result - (prev_result // 3) + 113 + (len(body) % 17) + (cmd % 23) + s + 7
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


class H5Encoder:
    """有状态的 H5 帧编码器。必须按顺序发送。"""

    def __init__(self, uid: int, version: int = VERSION_H5):
        self.uid = uid & 0xFFFFFFFF
        self.version = version & 0xFF
        self.result = 0

    def pack(self, cmd: int, args: Iterable[Any] | None = None) -> bytes:
        body = serialize_args(args)
        self.result = result_formula(self.result, cmd, body)
        return pack_h5(cmd, body, uid=self.uid, result=self.result, version=self.version)

    def reset(self) -> None:
        self.result = 0


class FlashEncoder:
    def __init__(self, uid: int):
        self.uid = uid & 0xFFFFFFFF
        self.result = 0

    def pack(self, cmd: int, args: Iterable[Any] | None = None, *, result: int | None = None) -> bytes:
        body = serialize_args(args)
        if result is not None:
            self.result = result
        return pack_flash(cmd, body, uid=self.uid, result=self.result)