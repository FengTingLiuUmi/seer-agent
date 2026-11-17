#!/usr/bin/env python3
"""实验用：连 seerproto -serve，等 ready，按给定 cmd 列表发命令并收回包。

    python tools/probe_serve.py 127.0.0.1:7811 2303 2301:0000008f 2313

body 用 `cmd:hex` 形式给。输出每条 C2S/S2C 的摘要，最后把回包 body 存到 bodies/<cmd>.bin。
"""
import json
import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(os.path.dirname(HERE), 'bodies')


class Conn:
    def __init__(self, addr, timeout=60):
        host, port = addr.rsplit(':', 1)
        self.s = socket.create_connection((host, int(port)), timeout=timeout)
        self.buf = b''

    def read(self, t=5):
        self.s.settimeout(t)
        while b'\n' not in self.buf:
            c = self.s.recv(65536)
            if not c:
                return None
            self.buf += c
        line, self.buf = self.buf.split(b'\n', 1)
        return json.loads(line)

    def send(self, obj):
        self.s.sendall((json.dumps(obj) + '\n').encode())


def main():
    addr = sys.argv[1]
    specs = sys.argv[2:]
    c = Conn(addr)
    t0 = time.time()
    ready = False
    while time.time() - t0 < 30:
        m = c.read(10)
        if not m:
            print('conn closed before ready')
            return 2
        print('< %-6s %s %s' % (m.get('type'), m.get('cmd', ''), m.get('name', '')))
        if m.get('type') == 'ready':
            ready = True
            break
        if m.get('type') == 'error':
            print('serve error:', m.get('error'))
            return 2
    if not ready:
        print('no ready')
        return 2
    print('READY %.1fs' % (time.time() - t0))

    os.makedirs(BODIES, exist_ok=True)
    for i, spec in enumerate(specs, 1):
        cmd, _, body = spec.partition(':')
        req = {'id': i, 'cmd': int(cmd)}
        if body:
            req['bodyHex'] = body
        print('\n>>> %s id=%d' % (spec, i))
        c.send(req)
        deadline = time.time() + 5
        hit = None
        while time.time() < deadline:
            try:
                m = c.read(1.5)
            except socket.timeout:
                break
            if not m:
                print('  <EOF>')
                return 3
            ty = m.get('type')
            if ty == 'error':
                print('  <ERR> %s' % m.get('error'))
                return 3
            if ty == 'c2s':
                print('  c2s cmd=%-6s %-24s res=%s' % (m.get('cmd'), m.get('name', ''), m.get('res')))
                continue
            if ty == 's2c':
                print('  s2c cmd=%-6s %-24s len=%-5s res=%-5s body=%s' % (
                    m.get('cmd'), m.get('name', ''), m.get('len'), m.get('res'), (m.get('bodyHex') or '')[:64]))
                if m.get('cmd') == int(cmd):
                    hit = m
                    break
        if hit:
            b = bytes.fromhex(hit.get('bodyHex') or '')
            path = os.path.join(BODIES, '%d.bin' % int(cmd))
            with open(path, 'wb') as f:
                f.write(b)
            print('  SAVED %s (%d bytes)' % (path, len(b)))
        else:
            print('  (no matching s2c)')
    print('\nDONE %.1fs' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())