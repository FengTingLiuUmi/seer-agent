"""登录链路（HTTP + 会话组装）。

2.0.9 字符串证据（镜像 RVA）：
  0x8c5a40  ``http://account-co.61.com/index.php?r=userIdentity/authenticate&callback=jQuery...``
  0x8c59ea  ``&game=02&tad=none&_=``
  0x8c59ff  ``&rememberPwd=true&vericode=``
  0x8c5a1b  ``&rememberAcc=false&passwd=``
  0x8c5a36  ``&account=``
  0x8c5aac  ``result`` / 0x8c5ab5 ``err_desc`` / 0x8c5abe ``data.uid`` / 0x8c5ac7 ``data.session``
  0x8c6474  ``https://seerh5login.61.com/online_gate?is_ssl=1``
  0xb84242  OAuth redirect URL / appid 20210906002 / duid
  0xc25cf9  ``https://account-co.61.com/v3?r=authorization/success``
  0xc25de9  ``https://account-co.61.com/v3/?r=token/trans``

2.0.7 反编译进一步确认：
  authenticate 返回 ``data.uid`` / ``data.session``；
  OAuth 回调的 ``code`` 交给 ``token/trans`` 换成 token；
  ``online_gate`` 返回 ``host:port``，随后 ``wss://host:port/``。
"""
from __future__ import annotations

import hashlib
import http.cookiejar
import json
import random
import re
import struct
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APPID = "20210906002"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
)
REFERER = "https://seerh5.61.com/"
UNITY_IP_URL = "https://seer-login-ip.61.com/unity-ip.txt"
UNITY_FALLBACK_HOST = "111.229.168.25"  # 2.0.9 的 unity 兜底 IP（镜像 0x8cad1d）
# 2.0.9 FUN_0044b723 反编译：游戏端口 = random(0x4b2=1202, 0x4ce=1230)；
#                         1001 body @0x50 serverId = random(0x5dc=1500, 0x708=1800)。
UNITY_PORT_RANGE = (0x4B2, 0x4CE)   # 1202..1230
UNITY_SERVERID_RANGE = (0x5DC, 0x708)  # 1500..1800


def _pick_unity_ip(text: str) -> str:
    """从 unity-ip.txt 响应里随机取一个 IP（忽略 1863/1864 端口）。

    对应 FUN_0044c1da：按 ``|`` 拆 → 随机取一项 → 按 ``:`` 拆 → 取 IP。
    拆失败/为空时兜底 111.229.168.25。
    """
    entries = [e.strip() for e in text.strip().strip('"').split("|") if e.strip()]
    if entries:
        entry = random.choice(entries)
        host = entry.split(":")[0].replace("http://", "").replace("https://", "").strip()
        if host:
            return host
    return UNITY_FALLBACK_HOST


def get_unity_gateway(client: HttpClient | None = None, *, timeout: float = 15.0) -> tuple[str, int]:
    """Unity 真机 1001 入口：随机 IP + 随机游戏端口（1202..1230）。

    unity-ip.txt 只给 IP 与 1863/1864，但 1863/1864 是旧 Flash/网关端口、被忽略；
    真实游戏端口由客户端在 [1202,1230] 随机选（FUN_0044b723）。
    """
    c = client or HttpClient(timeout=timeout)
    try:
        _, text, _ = c.request(UNITY_IP_URL, headers={"Accept": "*/*"})
    except Exception:
        text = ""
    host = _pick_unity_ip(text)
    port = random.randint(*UNITY_PORT_RANGE)
    return host, port


AUTH_URL = (
    "http://account-co.61.com/index.php?r=userIdentity/authenticate&callback="
    "jQuery19008830978978300397_"
)
TOKEN_TRANS_URL = "https://account-co.61.com/v3/?r=token/trans"
AUTH_SUCCESS_URL = "https://account-co.61.com/v3?r=authorization/success"
ONLINE_GATE_URL = "https://seerh5login.61.com/online_gate?is_ssl=1"
OAUTH_AUTHORIZE_URL = "https://account-co.61.com/v3/"


class LoginError(RuntimeError):
    pass


@dataclass(slots=True)
class LoginSession:
    uid: int
    session: str
    token: str | None = None
    gateway: str | None = None
    host: str | None = None
    port: int | None = None
    path: str = "/"
    mode: str = "flash"
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def sid(self) -> str:
        """2.0.21 证据：sid = uid 4 字节 BE + session 16 字节，hex。"""
        s = bytes.fromhex(self.session) if _is_hex(self.session) else self.session.encode("utf-8")
        return (struct.pack(">I", self.uid & 0xFFFFFFFF) + s[:16]).hex()

    def masked(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "session": (self.session[:6] + "..." + self.session[-4:]) if self.session else "",
            "token": (self.token[:8] + "...") if self.token else None,
            "gateway": self.gateway,
            "mode": self.mode,
        }


def _is_hex(s: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]+", s or "")) and len(s) % 2 == 0


def md5_password(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


class HttpClient:
    def __init__(self, timeout: float = 15.0, *, proxy: str | None = None):
        self.jar = http.cookiejar.CookieJar()
        handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPCookieProcessor(self.jar)]
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        self.opener = urllib.request.build_opener(*handlers)
        self.timeout = timeout

    def cookie_header(self) -> str:
        return "; ".join(f"{c.name}={c.value}" for c in self.jar)

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        h = {"User-Agent": UA, "Referer": REFERER}
        c = self.cookie_header()
        if c:
            h["Cookie"] = c
        h.update(headers or {})
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        with self.opener.open(req, timeout=self.timeout) as r:
            raw = r.read()
            text = _decode_body(raw, r.headers.get_content_charset())
            return r.status, text, dict(r.headers)


def _decode_body(raw: bytes, charset: str | None) -> str:
    for enc in filter(None, [charset, "utf-8", "gbk"]):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _json_from(text: str) -> dict[str, Any]:
    text = text.strip()
    # JSONP: jQuery...({...});
    if text.startswith("jQuery") or text.startswith("jQuery"):
        m = re.search(r"\((.*)\)\s*;?\s*$", text, re.S)
        if m:
            text = m.group(1)
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                v = json.loads(m.group(0))
                return v if isinstance(v, dict) else {}
            except json.JSONDecodeError:
                pass
    return {}


def authenticate(
    account: str,
    password: str,
    *,
    client: HttpClient | None = None,
    timeout: float = 15.0,
) -> LoginSession:
    """Flash/账号密码登录：userIdentity/authenticate → uid + session。"""
    c = client or HttpClient(timeout=timeout)
    ts = int(time.time() * 1000) + random.randint(0, 999)
    url = (
        AUTH_URL
        + f"&account={urllib.parse.quote(str(account))}"
        + "&rememberAcc=false&passwd="
        + md5_password(password)
        + "&rememberPwd=true&vericode=&game=02&tad=none&_="
        + str(ts)
    )
    status, text, _ = c.request(url, headers={"Accept": "*/*"})
    data = _json_from(text)
    payload = data.get("data") or data
    uid = payload.get("uid") if isinstance(payload, dict) else None
    sess = payload.get("session") if isinstance(payload, dict) else None
    if not uid or not sess:
        err = data.get("err_desc") or data.get("result") or text[:200]
        raise LoginError(f"authenticate failed (HTTP {status}): {err}")
    # 2.0.9 FUN_0040f897：session 长度 > 0x1a 时截到 0x20（32 个 hex 字符）。
    sess = str(sess)
    if len(sess) > 32:
        sess = sess[:32]
    return LoginSession(uid=int(uid), session=sess, mode="flash", raw=data)


_AUTH_CACHE: dict[str, tuple[float, "LoginSession"]] = {}


def authenticate_cached(account: str, password: str, *, ttl: float = 1800.0) -> "LoginSession":
    """鉴权结果缓存（默认 30 分钟），避免重复读取时反复走 account-co 鉴权。"""
    import time

    now = time.time()
    hit = _AUTH_CACHE.get(account)
    if hit and now - hit[0] < ttl:
        return hit[1]
    sess = authenticate(account, password)
    _AUTH_CACHE[account] = (now, sess)
    return sess


def oauth_authorize_url(duid: str | None = None, state: str | None = None) -> str:
    """Unity 登录页地址；2.0.9 反编译中的 v3 OAuth 入口。"""
    duid = duid or random_duid()
    state = state or random_duid()
    q = urllib.parse.urlencode(
        {
            "r": "authorization",
            "appid": APPID,
            "scope": "userinfo",
            "duid": duid,
            "source": "0",
            "register": "",
            "bg": "0",
            "redirect_url": AUTH_SUCCESS_URL,
            "tad": "unknown",
            "state": state,
        },
        quote_via=urllib.parse.quote,
    )
    return OAUTH_AUTHORIZE_URL + "?" + q


def extract_code(url_or_code: str) -> str:
    """从回调 URL / 纯 code 中取出 code。"""
    s = url_or_code.strip()
    if "code=" in s:
        q = urllib.parse.urlparse(s).query
        vals = urllib.parse.parse_qs(q)
        if vals.get("code"):
            return vals["code"][0]
        m = re.search(r"[?&]code=([^&]+)", s)
        if m:
            return urllib.parse.unquote(m.group(1))
    return s


def exchange_code(code: str, *, duid: str, client: HttpClient | None = None, timeout: float = 15.0) -> str:
    """OAuth code → token（token/trans）。"""
    c = client or HttpClient(timeout=timeout)
    q = urllib.parse.urlencode({"appid": APPID, "duid": duid, "code": extract_code(code)})
    url = TOKEN_TRANS_URL + "&" + q
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://account-co.61.com",
        "Referer": "https://account-co.61.com/",
    }
    status, text, _ = c.request(url, method="POST", body=b"", headers=headers)
    token = text.strip().strip('"')
    # 兼容 {"data":"..."} / {"token":"..."}
    if token.startswith("{"):
        j = _json_from(token)
        token = str(j.get("data") or j.get("token") or "").strip()
    if not token:
        raise LoginError(f"token/trans failed (HTTP {status}): {text[:200]}")
    return token


def refresh_token(uid: int, refresh: str, *, duid: str, client: HttpClient | None = None) -> str:
    c = client or HttpClient()
    body = urllib.parse.urlencode(
        {"appid": APPID, "uid": str(uid), "duid": duid, "refresh_token": refresh}
    ).encode()
    status, text, _ = c.request(
        "https://account-co.61.com/v3/token/refresh",
        method="POST",
        body=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    j = _json_from(text)
    token = (j.get("data") or {}).get("token") if isinstance(j.get("data"), dict) else j.get("token")
    if not token:
        raise LoginError(f"token/refresh failed (HTTP {status}): {text[:200]}")
    return str(token)


def get_gateway(client: HttpClient | None = None, *, timeout: float = 15.0, retries: int = 10) -> str:
    """online_gate，最多重试 10 次；失败时用 2.0.9 的硬编码兜底。"""
    c = client or HttpClient(timeout=timeout)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "referer": "https://seerh5.61.com/",
        "user-agent": UA,
    }
    last = ""
    for _ in range(max(1, retries)):
        status, text, _ = c.request(ONLINE_GATE_URL, headers=headers)
        gw = text.strip()
        if status == 200 and gw:
            return gw
        last = f"HTTP {status}: {text[:120]}"
    # 2.0.9 FUN_00419d21 的兜底字符串
    if last:
        return "123.207.217.117:3007"
    raise LoginError(f"online_gate failed: {last}")


def parse_gateway(gateway: str) -> tuple[str, int, str]:
    """``h5gy.61.com/wss_online_02/:3002`` / ``1.2.3.4:3007`` → host, port, path。"""
    s = gateway.strip().strip('"')
    m = re.match(r"^([^/:]+)(/[^:]*)?:(\d{2,5})$", s)
    if m:
        return m.group(1), int(m.group(3)), m.group(2) or "/"
    m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})$", s)
    if m:
        return m.group(1), int(m.group(2)), "/"
    # JSON 形式 {"host": "...", "port": ...}
    try:
        j = json.loads(s)
        if isinstance(j, dict) and j.get("host"):
            return str(j["host"]), int(j.get("port") or 443), str(j.get("path") or "/")
    except Exception:
        pass
    raise LoginError(f"cannot parse gateway: {gateway!r}")


def random_duid(n: int = 32) -> str:
    alphabet = "0123456789abcdef"
    return "".join(random.choice(alphabet) for _ in range(n))


# ---------------------------------------------------------------------------
# 登录包

_TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "login_template.bin"


def _default_template() -> bytearray:
    if _TEMPLATE_PATH.exists():
        b = bytearray(_TEMPLATE_PATH.read_bytes())
        if len(b) >= 508:
            return b
    b = bytearray(508)
    b[0x52:0x54] = struct.pack(">H", 3002)
    b[0x54:0x58] = struct.pack(">I", 1)
    b[0x58:0x5A] = b"PC"
    b[0x6c:0x70] = struct.pack(">I", 10101)
    _put_cstr(b, 0x7C, b"unity_webgl_h5", 0x98 - 0x7C)
    _put_cstr(b, 0x98, b"com.taomee.seer.mobile", 0x178 - 0x98)
    _put_cstr(b, 0x178, b"Edge157.0.0.0", 0x1FC - 0x178)
    return b


def _put_cstr(buf: bytearray, off: int, value: bytes, size: int) -> None:
    if value and len(value) >= size:
        value = value[: size - 1]
    buf[off:off + size] = value + b"\x00" * (size - len(value))


def build_h5_login_body(
    session: LoginSession,
    *,
    area_id: int | None = None,
    gate_id: int | None = None,
    platform: str = "unity_app_taomee",
    ua: str | None = None,
    template: bytes | None = None,
) -> bytes:
    """构造 cmd 1001 的登录 body。

    508 字节模板来自官方 H5 客户端；字段偏移见 ``docs/协议与登录.md``。
    2.0.9 的 ``online_gate`` 返回的端口写 0x52，区号写 0x54；平台串写 0x7c。
    """
    b = bytearray(template) if template is not None else _default_template()
    if len(b) < 508:
        b.extend(b"\x00" * (508 - len(b)))
    sess = bytes.fromhex(session.session) if _is_hex(session.session) else session.session.encode()
    b[0:16] = (sess + b"\x00" * 16)[:16]
    if gate_id is None and session.port:
        gate_id = session.port
    if gate_id is not None:
        b[0x52:0x54] = struct.pack(">H", gate_id & 0xFFFF)
    if area_id is not None:
        b[0x54:0x58] = struct.pack(">I", area_id & 0xFFFFFFFF)
    _put_cstr(b, 0x58, b"PC", 4)
    _put_cstr(b, 0x7C, platform.encode(), 0x98 - 0x7C)
    _put_cstr(b, 0x98, b"com.taomee.seer.mobile", 0x178 - 0x98)
    if ua:
        _put_cstr(b, 0x178, ua.encode(), 0x1FC - 0x178)
    return bytes(b)


def build_unity_login_body(
    session: LoginSession,
    *,
    gate_id: int | None = None,
    area_id: int = 1,
    platform: str = "unity_app_taomee",
    ua: str | None = None,
) -> bytes:
    """Unity 真机 1001 body（508B）。字段布局按 FUN_0044b723 反编译 + 官方抓包校准：

      0x00 16B session
      0x10 "taomee"（64B）
      0x50 u32 serverId（随机 1500..1800；0x52 只是它的低 16 位）
      0x54 u32 area_id=1
      0x58 "PC"（16B）
      0x68 u32 10100
      0x6c u32 1
      0x70 u32 1
      0x74 u32 2
      0x78 "unity_app_taomee"（32B）
      0x98 "com.taomee.seer.mobile"（32B）
      0x178 UA（默认官方主板型号）
    """
    if gate_id is None:
        gate_id = random.randint(*UNITY_SERVERID_RANGE)
    b = bytearray(508)
    sess = bytes.fromhex(session.session) if _is_hex(session.session) else session.session.encode()
    b[0:16] = (sess + b"\x00" * 16)[:16]
    _put_cstr(b, 0x10, b"taomee", 0x50 - 0x10)
    b[0x50:0x54] = struct.pack(">I", gate_id & 0xFFFFFFFF)
    b[0x54:0x58] = struct.pack(">I", area_id & 0xFFFFFFFF)
    _put_cstr(b, 0x58, b"PC", 0x10)
    b[0x68:0x6C] = struct.pack(">I", 10100)
    b[0x6C:0x70] = struct.pack(">I", 1)
    b[0x70:0x74] = struct.pack(">I", 1)
    b[0x74:0x78] = struct.pack(">I", 2)
    _put_cstr(b, 0x78, platform.encode(), 0x20)
    _put_cstr(b, 0x98, b"com.taomee.seer.mobile", 0xE0)
    if ua:
        _put_cstr(b, 0x178, ua.encode(), 0x84)
    else:
        _put_cstr(b, 0x178, b"MS-7D76(Micro-StarInternationalCo.,Ltd.)", 0x84)
    return bytes(b)


def build_flash_login(session: LoginSession) -> bytes:
    """Flash 登录帧（cmd 1001）。

    依据 2.0.9 FUN_0044ae52：
      local_18 = 0x8ca151 -> "000000010000000100000001000...000"
      local_1c = FUN_00419fcd(&local_18)   // hex -> 20 字节
      FUN_00418e9b(0x3e9, &local_1c)       // cmd 1001
    """
    from .protocol import pack_flash

    body = bytes.fromhex(
        "0000000100000001000000010000000000000000000000000000000000000000000000000000000000000000"
    )
    return pack_flash(1001, body, uid=session.uid, result=0)


def make_sid(uid: int, session_hex: str) -> bytes:
    return struct.pack(">I", uid & 0xFFFFFFFF) + bytes.fromhex(session_hex)[:16]