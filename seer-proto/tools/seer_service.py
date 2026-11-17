#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seer-service —— 赛尔号「新登录界面 + 操作接口」的常驻代理。

一个进程管理整条会话，避免同账号多连接互踢：
  * 登录：调 tools/prep_pwd.mjs 拿一次性 session → 启动 seerproto.exe -serve
  * 收发：通过 serve 的 JSON 行协议下发 cmd / 收 S2C 帧，维护状态与事件环形缓冲
  * 对外：REST（登录界面 / MCP / 其它 agent 共用同一会话）

用法:
  python tools/seer_service.py [--port 7820] [--serve-port 7811] [--view-port 7812]
  python tools/seer_service.py --autologin           # 启动后自动登录

REST:
  GET  /api/status                   会话状态
  POST /api/login                    {"account":"..."} 登录（会先等冷却）
  POST /api/logout                   断开
  POST /api/send                     {"cmd":2303,"bodyHex":"","waitMs":5000,"expect":true}
  GET  /api/pets                     精灵列表（解码 2303）
  GET  /api/state                    最新游戏快照（玩家/地图/精灵/成就…）
  GET  /api/events?since=N&limit=M   事件增量
  GET  /                             登录界面
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
import urllib.parse
import http.server
import socketserver

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # seer-proto
WORK = os.path.dirname(ROOT)                 # workspace
BODIES = os.path.join(ROOT, 'bodies')
LOGIN_JSON = os.path.join(ROOT, 'login.json')
LOCK = os.path.join(ROOT, '.seerproto.lock')
EXE = os.path.join(ROOT, 'seerproto.exe')
UI_DIR = os.path.join(ROOT, 'ui')
DEFAULT_ACCOUNT = 'ACCOUNT'

# ---------------------------------------------------------------- 状态


class Session:
    """一条 seerproto 会话 + 它暴露的 serve 连接。"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = None
        self.sock = None
        self.lock = threading.RLock()
        self.events = []
        self.event_seq = 0
        self.state = new_state()
        self.ready = False
        self.started_at = None
        self.ready_at = None
        self.dead_reason = None
        self.waiters = {}                  # id -> [frames]
        self.ready_evt = threading.Event()
        self._rx = None

    # -- serve 连接 -------------------------------------------------
    def connect_serve(self, timeout=30.0):
        host, port = self.cfg.serve_host, self.cfg.serve_port
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                s = socket.create_connection((host, port), timeout=2.0)
                s.settimeout(None)
                self.sock = s
                self._rx = threading.Thread(target=self._reader, daemon=True)
                self._rx.start()
                return True
            except OSError as e:
                last = e
                time.sleep(0.25)
        self.dead_reason = 'serve 连接失败: %s' % last
        return False

    def _reader(self):
        buf = b''
        while True:
            try:
                chunk = self.sock.recv(65536)
            except OSError as e:
                self.dead_reason = self.dead_reason or ('recv: %s' % e)
                break
            if not chunk:
                self.dead_reason = self.dead_reason or 'serve 连接关闭'
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                self._on_msg(msg)
        self.ready = False

    def _on_msg(self, msg):
        ty = msg.get('type')
        with self.lock:
            if ty == 'ready':
                self.ready = True
                self.ready_at = time.time()
                self.ready_evt.set()
                self._push({'type': 'ready', 'text': '已进入世界（引导完成）'})
                return
            if ty == 'error':
                self.dead_reason = msg.get('error') or 'serve error'
                self._push({'type': 'error', 'text': '连接错误: %s' % self.dead_reason})
                return
            if ty == 'bye':
                self.dead_reason = self.dead_reason or 'serve bye'
                self._push({'type': 'bye', 'text': '会话结束'})
                return
            ev = {
                'type': ty,
                'id': msg.get('id'),
                'cmd': msg.get('cmd'),
                'name': msg.get('name') or '',
                'len': msg.get('len'),
                'res': msg.get('res'),
                'bodyHex': msg.get('bodyHex') or '',
            }
            self._push(ev)
            if ty == 's2c':
                self._apply_state(ev)
                rid = msg.get('id')
                if rid in self.waiters:
                    self.waiters[rid].append(ev)

    def _push(self, ev):
        ev['t'] = int(time.time() * 1000)
        self.event_seq += 1
        ev['seq'] = self.event_seq
        self.events.append(ev)
        if len(self.events) > 4000:
            del self.events[:1000]

    def send_raw(self, req):
        if not self.sock or not self.ready:
            raise RuntimeError('未连接或尚未 ready')
        self.sock.sendall((json.dumps(req) + '\n').encode())

    def call(self, cmd, body_hex='', wait_ms=5000, expect=True):
        """发一条命令并等它的 S2C 回包。

        serve 的 S2C 不带稳定的请求 id（auto 引导帧也会刷新它），所以按
        「cmd + 发送后的序号」收集，兼容服务端把 id 附在帧上的情况。
        """
        rid = uuid.uuid4().hex[:8]
        req = {'id': rid, 'cmd': int(cmd)}
        if body_hex:
            req['bodyHex'] = body_hex
        with self.lock:
            since = self.event_seq
        self.send_raw(req)
        if not expect:
            return {'id': rid, 'cmd': int(cmd), 'frames': []}
        deadline = time.time() + wait_ms / 1000.0
        frames = []
        while time.time() < deadline:
            with self.lock:
                frames = [e for e in self.events
                          if e.get('seq', 0) > since and e.get('type') == 's2c'
                          and e.get('cmd') == int(cmd)]
            if frames:
                break
            time.sleep(0.05)
        return {'id': rid, 'cmd': int(cmd), 'frames': frames}

    # -- 状态推进 ---------------------------------------------------
    def _apply_state(self, ev):
        cmd = ev.get('cmd')
        try:
            body = bytes.fromhex(ev.get('bodyHex') or '')
        except ValueError:
            body = b''
        try:
            if cmd == 2001:
                self.state['map'] = decode_2001(body)
                self.state['entered'] = True
            elif cmd == 2003:
                self.state['players'] = decode_2003(body)
            elif cmd == 2303:
                self.state['pets'] = decode_2303(body)
            elif cmd == 2301:
                info = decode_2301(body)
                if info:
                    self.state['last_pet_info'] = info
            elif cmd == 3401:
                self.state['achievements'] = {'count': be32(body, 0)}
            elif cmd == 1001 and ev.get('res') not in (None, 0):
                self.state['login_res'] = ev.get('res')
        except Exception as e:
            self.state.setdefault('decode_errors', []).append('%s: %s' % (cmd, e))

    def stop(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.ready = False


def new_state():
    return {
        'entered': False,
        'map': None,
        'players': [],
        'pets': [],
        'last_pet_info': None,
        'achievements': None,
        'login_res': None,
    }


# ---------------------------------------------------------------- 解码


def be32(b, off=0):
    if len(b) < off + 4:
        return None
    return int.from_bytes(b[off:off + 4], 'big')


def utf8_runs(b, minlen=2):
    """从二进制里抽出连续 UTF-8 中文/ASCII 片段（用于昵称等定长字段）。"""
    out = []
    cur = bytearray()
    i = 0
    while i < len(b):
        c = b[i]
        if 0x20 <= c < 0x7f or c >= 0x80:
            cur.append(c)
            i += 1
            continue
        if len(cur) >= minlen:
            try:
                out.append(bytes(cur).decode('utf-8'))
            except Exception:
                pass
        cur = bytearray()
        i += 1
    if len(cur) >= minlen:
        try:
            out.append(bytes(cur).decode('utf-8'))
        except Exception:
            pass
    return out


def decode_2001(b):
    """ENTER_MAP：地图名 = 首个 CJK 串；昵称 = 之后最长的 CJK 串（两者都会变长，不能按定长切）。"""
    if not b:
        return None
    out = {'len': len(b)}
    runs = [n for n in utf8_runs(b, 2) if _looks_name(n)]
    # 名字区域：从 0x14 之后开始（0x00-0x13 是时间戳/token）
    tail = b[0x14:]
    cands = [n for n in utf8_runs(tail, 2) if _looks_name(n)]
    if cands:
        out['map_name'] = cands[0] if len(cands[0]) <= 12 else None
        nick_cands = [n for n in cands if n != out.get('map_name')]
        if nick_cands:
            out['nick'] = max(nick_cands, key=len)
        elif cands:
            out['nick'] = cands[0]
    elif runs:
        out['nick'] = max(runs, key=len)
    out['names'] = sorted(set(cands or runs), key=len, reverse=True)[:8]
    return out


def _looks_name(s):
    if not s or len(s) < 2 or len(s) > 18:
        return False
    if any(0xFFFD <= ord(c) or ord(c) < 0x20 for c in s):
        return False
    cjk = sum(1 for c in s if 0x4E00 <= ord(c) <= 0x9FFF)
    return cjk >= 1 or s.isalnum()


def decode_2003(b):
    """LIST_MAP_PLAYER：count + 每项玩家。先用启发式（昵称列表）。"""
    if not b:
        return []
    count = be32(b, 0) or 0
    names = utf8_runs(b, 2)
    out = [{'name': n} for n in names[:32]]
    if count and len(out) > count:
        out = out[:count]
    return out


def decode_2303(b):
    """GET_PET_LIST：先给出 count + 原始 hex；字段布局待实战校准。"""
    if not b:
        return []
    count = be32(b, 0)
    return [{'count': count, 'len': len(b), 'hex': b.hex()}]


def decode_2301(b):
    if not b:
        return None
    return {'len': len(b), 'head': b[:48].hex(), 'names': utf8_runs(b, 2)[:8],
            'ints': [be32(b, i) for i in range(0, min(len(b), 48) - 3, 4)]}


# ---------------------------------------------------------------- 服务


class Cfg:
    def __init__(self, a):
        self.port = a.port
        self.serve_host = '127.0.0.1'
        self.serve_port = a.serve_port
        self.view_port = a.view_port
        self.account = a.account
        self.login_cooldown = a.login_cooldown
        self.seconds = a.seconds
        self.enable_view = not a.no_view


def tail(path, n):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode('utf-8', 'replace')
    except OSError:
        return ''


def load_cmd_ids():
    """{名称: cmd}，名称大小写不敏感。"""
    path = os.path.join(ROOT, 'data', 'commandid.json')
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return {}
    return {str(k).upper(): int(v) for k, v in raw.items() if isinstance(v, (int, float))}


CMD_IDS = load_cmd_ids()
CMD_NAMES = {}
for _n, _id in CMD_IDS.items():
    CMD_NAMES.setdefault(_id, _n)


def resolve_cmd(v):
    """接受 2303 / '2303' / 'GET_PET_LIST'。"""
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    cid = CMD_IDS.get(s.upper())
    if cid is None:
        raise ValueError('未知命令名: %s' % s)
    return cid


class Service:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sess = None
        self.login_lock = threading.Lock()
        self.last_login = 0
        self.last_error = None
        self.start_time = time.time()

    # -- 状态 -------------------------------------------------------
    def status(self):
        s = self.sess
        o = {
            'ok': True,
            'account': self.cfg.account,
            'logged_in': bool(s and s.ready and not s.dead_reason),
            'ready': bool(s and s.ready),
            'process': bool(s and s.proc and s.proc.poll() is None),
            'serving': '%s:%s' % (self.cfg.serve_host, self.cfg.serve_port),
            'view': ('http://127.0.0.1:%d' % self.cfg.view_port) if self.cfg.enable_view else None,
            'dead_reason': (s.dead_reason if s else None) or self.last_error,
            'started_at': s.started_at if s else None,
            'ready_at': s.ready_at if s else None,
            'uptime': round(time.time() - self.start_time, 1),
            'event_seq': s.event_seq if s else 0,
            'state': s.state if s else new_state(),
            'login_cooldown_left': max(0, int(self.cfg.login_cooldown - (time.time() - self.last_login))) if self.last_login else 0,
            'last_login': self.last_login,
        }
        return o

    def ensure_started(self):
        if self.sess and self.sess.proc and self.sess.proc.poll() is None:
            return self.sess
        raise RuntimeError('会话未启动')

    # -- 登录 -------------------------------------------------------
    def login(self, account=None, password=None, force=False, timeout=75, boot=None):
        """prep_pwd → seerproto(-serve) → 等 ready。password 为空时用本机加密凭据。
        boot='ack' 时让引导先回 45963 再发 42494（用于实测两种进世界时序）。"""
        account = account or self.cfg.account
        with self.login_lock:
            if self.sess and self.sess.ready and not force:
                return {'ok': True, 'already': True, 'status': self.status()}
            wait = self.cfg.login_cooldown - (time.time() - self.last_login) if self.last_login else 0
            if wait > 0:
                time.sleep(min(wait, 30))
            self._teardown()
            t0 = time.time()
            try:
                env = dict(os.environ)
                if password:
                    env['SEER_PASSWORD'] = password     # 经环境变量传给 prep_pwd，不出现在命令行
                prep = subprocess.run(
                    ['node', os.path.join(HERE, 'prep_pwd.mjs'), account],
                    cwd=ROOT, capture_output=True, text=True, timeout=120,
                    encoding='utf-8', errors='replace', env=env)
            except Exception as e:
                self.last_error = 'prep 启动失败: %s' % e
                raise RuntimeError(self.last_error)
            if prep.returncode != 0 or not os.path.exists(LOGIN_JSON):
                self.last_error = '登录准备失败: %s %s' % ((prep.stdout or '')[-500:], (prep.stderr or '')[-300:])
                raise RuntimeError(self.last_error)
            self.last_login = time.time()
            try:
                os.remove(LOCK)
            except OSError:
                pass
            args = [EXE, '-info', LOGIN_JSON,
                    '-serve', '127.0.0.1:%d' % self.cfg.serve_port,
                    '-seconds', str(self.cfg.seconds),
                    '-log', 'session.jsonl',
                    '-cmdmap', os.path.join(ROOT, 'data', 'commandid.json')]
            if self.cfg.enable_view:
                args += ['-view', '127.0.0.1:%d' % self.cfg.view_port]
            out_path = os.path.join(ROOT, 'service-proto.out')
            err_path = os.path.join(ROOT, 'service-proto.err')
            fo = open(out_path, 'w', encoding='utf-8', errors='replace')
            fe = open(err_path, 'w', encoding='utf-8', errors='replace')
            cenv = dict(os.environ)
            if boot == 'ack':
                cenv['SEER_BOOT_ACK'] = '1'
            else:
                cenv.pop('SEER_BOOT_ACK', None)
            self.sess = Session(self.cfg)
            self.sess.proc = subprocess.Popen(args, cwd=ROOT, stdout=fo, stderr=fe, env=cenv,
                                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.sess.started_at = time.time()
            if self.sess.connect_serve(timeout=30):
                self.sess.ready_evt.wait(timeout=timeout)
            ready = self.sess.ready
            st = self.status()
            st['ok'] = ready
            st['elapsed'] = round(time.time() - t0, 1)
            if not ready:
                st['error'] = self.sess.dead_reason or ('等待 ready 超时（%ss）' % timeout)
                st['prep_out'] = (prep.stdout or '')[-300:]
                st['proto_out'] = tail(out_path, 1500)
                st['proto_err'] = tail(err_path, 800)
            return st

    def _teardown(self):
        if self.sess:
            self.sess.stop()
            self.sess = None

    def logout(self):
        self._teardown()
        try:
            os.remove(LOCK)
        except OSError:
            pass
        return {'ok': True, 'status': self.status()}

    # -- 命令 -------------------------------------------------------
    def send(self, cmd, body_hex='', wait_ms=5000, expect=True):
        s = self.ensure_started()
        if not s.ready:
            raise RuntimeError('会话尚未 ready（%s）' % (s.dead_reason or '引导中'))
        return s.call(cmd, body_hex=body_hex, wait_ms=wait_ms, expect=expect)

    def events(self, since=0, limit=200):
        s = self.sess
        if not s:
            return []
        with s.lock:
            evs = [e for e in s.events if e.get('seq', 0) > since]
        return evs[-limit:] if limit else evs


# ---------------------------------------------------------------- HTTP


def make_handler(svc):
    class H(http.server.BaseHTTPRequestHandler):
        server_version = 'seer-service/0.1'

        def _send(self, obj, code=200, ctype='application/json; charset=utf-8'):
            if isinstance(obj, bytes):
                body = obj
            elif isinstance(obj, str):
                body = obj.encode('utf-8')
            else:
                body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            n = int(self.headers.get('Content-Length') or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode('utf-8'))
            except Exception:
                return {}

        def _ok(self, *a, **kw):
            try:
                return self._send(*a, **kw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _send_file(self, name):
            base = os.path.abspath(UI_DIR)
            path = os.path.abspath(os.path.join(base, name))
            if not (path == base or path.startswith(base + os.sep)):
                return self._ok({'ok': False, 'error': 'bad path'}, 403)
            try:
                with open(path, 'rb') as f:
                    data = f.read()
            except OSError:
                return self._ok({'ok': False, 'error': 'missing %s' % name}, 404)
            ctype = 'text/html; charset=utf-8'
            if path.endswith('.js'):
                ctype = 'application/javascript; charset=utf-8'
            elif path.endswith('.css'):
                ctype = 'text/css; charset=utf-8'
            elif path.endswith('.png'):
                ctype = 'image/png'
            elif path.endswith('.json'):
                ctype = 'application/json; charset=utf-8'
            return self._send(data, ctype=ctype)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            p = u.path
            if p in ('/', '/index.html'):
                return self._send_file('index.html')
            if p.startswith('/ui/'):
                return self._send_file(p[len('/ui/'):])
            if p == '/api/status':
                return self._ok(svc.status())
            if p == '/api/state':
                return self._ok({'ok': True, 'state': (svc.sess.state if svc.sess else new_state())})
            if p == '/api/events':
                since = int((q.get('since') or ['0'])[0] or 0)
                limit = int((q.get('limit') or ['200'])[0] or 200)
                return self._ok({'ok': True, 'events': svc.events(since, limit),
                                 'seq': svc.sess.event_seq if svc.sess else 0})
            if p == '/api/pets':
                return self._ok({'ok': True,
                                 'pets': (svc.sess.state.get('pets') if svc.sess else []),
                                 'state': (svc.sess.state if svc.sess else new_state())})
            if p == '/health':
                return self._ok({'ok': True})
            return self._ok({'ok': False, 'error': 'not found'}, 404)

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            p = u.path
            b = self._body()
            try:
                if p == '/api/login':
                    return self._ok(svc.login(b.get('account'), b.get('password'),
                                              force=bool(b.get('force', True)),
                                              boot=b.get('boot')))
                if p == '/api/logout':
                    return self._ok(svc.logout())
                if p == '/api/send':
                    target = b.get('cmd', b.get('name'))
                    r = svc.send(resolve_cmd(target),
                                 body_hex=(b.get('bodyHex') or ''),
                                 wait_ms=int(b.get('waitMs', 5000)),
                                 expect=bool(b.get('expect', True)))
                    return self._ok({'ok': True, 'frames': r.get('frames') or [], 'id': r.get('id')})
                if p == '/api/pets':
                    r = svc.send(2303, wait_ms=int(b.get('waitMs', 6000)))
                    frames = r.get('frames') or []
                    raw = b''
                    if frames:
                        try:
                            raw = bytes.fromhex(frames[0].get('bodyHex') or '')
                        except ValueError:
                            raw = b''
                    if raw:
                        os.makedirs(BODIES, exist_ok=True)
                        with open(os.path.join(BODIES, '2303.bin'), 'wb') as f:
                            f.write(raw)
                        svc.sess.state['pets'] = decode_2303(raw)
                    return self._ok({'ok': bool(frames), 'frames': frames, 'rawLen': len(raw),
                                     'pets': (svc.sess.state.get('pets') if svc.sess else [])})
                if p == '/api/petinfo':
                    r = svc.send(2301, body_hex=(b.get('bodyHex') or ''), wait_ms=int(b.get('waitMs', 6000)))
                    frames = r.get('frames') or []
                    info = None
                    if frames:
                        try:
                            raw = bytes.fromhex(frames[0].get('bodyHex') or '')
                        except ValueError:
                            raw = b''
                        info = decode_2301(raw)
                        if svc.sess:
                            svc.sess.state['last_pet_info'] = info
                    return self._ok({'ok': bool(frames), 'frames': frames, 'info': info})
            except Exception as e:
                return self._ok({'ok': False, 'error': str(e)}, 500)
            return self._ok({'ok': False, 'error': 'not found'}, 404)

        def log_message(self, fmt, *a):
            sys.stderr.write('%s %s\n' % (time.strftime('%H:%M:%S'), fmt % a))

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=7820)
    ap.add_argument('--serve-port', type=int, default=7811)
    ap.add_argument('--view-port', type=int, default=7812)
    ap.add_argument('--account', default=DEFAULT_ACCOUNT)
    ap.add_argument('--login-cooldown', type=int, default=45,
                    help='两次登录的最小间隔秒数（session 一次性，过快会被服务端踢）')
    ap.add_argument('--seconds', type=int, default=6 * 3600, help='seerproto 最长运行秒数')
    ap.add_argument('--no-view', action='store_true', help='不启 seerproto 自带看板')
    ap.add_argument('--autologin', action='store_true')
    a = ap.parse_args()

    cfg = Cfg(a)
    svc = Service(cfg)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', cfg.port), make_handler(svc))
    httpd.daemon_threads = True
    print('seer-service on http://127.0.0.1:%d  (ui=%s)' % (cfg.port, UI_DIR), flush=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if a.autologin:
        try:
            print(json.dumps(svc.login(), ensure_ascii=False)[:800], flush=True)
        except Exception as e:
            print('autologin failed: %s' % e, flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        svc.logout()
        httpd.shutdown()


if __name__ == '__main__':
    main()