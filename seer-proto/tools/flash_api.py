#!/usr/bin/env python3
"""Flash 宿主的 HTTP 接口（给大模型/agent 用）

宿主(host_play.ps1) 监听 llm-seer/ipc/cmd.json，本服务把 HTTP 请求翻译成文件命令。

用法: python tools/flash_api.py [--port 7801]
接口:
  GET  /state                -> 页面状态(JSON: title/url/flash/forAs/sid/frames)
  POST /eval  {"code":"..."} -> 在页面执行 JS，返回结果
  POST /key   {"keys":"..."} -> SendKeys（如 "{TAB}abc{ENTER}"）
  POST /click {"x":512,"y":330}
  POST /nav   {"url":"https://..."}
  POST /login                -> 盲注键盘登录（账号+密码+Enter）
"""
import argparse, json, os, sys, time, uuid
import http.server, socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IPC = os.path.join(os.path.dirname(ROOT), 'llm-seer', 'ipc')
CMDF = os.path.join(IPC, 'cmd.json')
RESPF = os.path.join(IPC, 'resp.json')
STATEF = os.path.join(IPC, 'state.json')


def call_host(op, timeout=15, **kw):
    os.makedirs(IPC, exist_ok=True)
    rid = uuid.uuid4().hex[:8]
    req = {'id': rid, 'op': op}
    req.update(kw)
    try:
        os.remove(RESPF)
    except OSError:
        pass
    tmp = CMDF + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(req, f, ensure_ascii=False)
    os.replace(tmp, CMDF)          # 原子写入，避免宿主读到半截
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(RESPF):
            try:
                with open(RESPF, encoding='utf-8-sig') as f:
                    resp = json.load(f)
                if resp.get('id') in (rid, None):
                    return resp
            except Exception:
                pass
        time.sleep(0.1)
    return {'id': rid, 'op': op, 'ok': False, 'error': 'host timeout (is host_play.ps1 running?)'}


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
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

    def do_GET(self):
        if self.path.startswith('/state'):
            try:
                with open(STATEF, encoding='utf-8-sig') as f:
                    raw = f.read()
                return self._send({'ok': True, 'state': json.loads(raw)})
            except Exception as e:
                return self._send({'ok': False, 'error': str(e)})
        if self.path.startswith('/health'):
            return self._send({'ok': True, 'host': os.path.exists(STATEF)})
        self._send({'ok': False, 'error': 'use /state /eval /key /click /nav /login'}, 404)

    def do_POST(self):
        b = self._body()
        p = self.path.split('?')[0].rstrip('/')
        if p == '/eval':
            return self._send(call_host('eval', code=b.get('code', '')))
        if p == '/key':
            return self._send(call_host('key', keys=b.get('keys', '')))
        if p == '/click':
            return self._send(call_host('click', x=int(b.get('x', 512)), y=int(b.get('y', 330))))
        if p == '/nav':
            return self._send(call_host('nav', url=b.get('url', '')))
        if p == '/login':
            return self._send(call_host('login'))
        if p == '/autologin':
            return self._send(call_host('autologin', timeout=120))
        if p == '/net':
            return self._send(call_host('net'))
        self._send({'ok': False, 'error': 'unknown endpoint'}, 404)

    def log_message(self, fmt, *a):
        sys.stderr.write('%s %s\n' % (time.strftime('%H:%M:%S'), fmt % a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=7801)
    a = ap.parse_args()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', a.port), H) as s:
        print('flash api on http://127.0.0.1:%d  (ipc=%s)' % (a.port, IPC), flush=True)
        s.serve_forever()


if __name__ == '__main__':
    main()