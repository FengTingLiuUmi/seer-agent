#!/usr/bin/env python3
"""Flash 宿主的命令行 + 网络状态工具（给 agent 直接用；MCP 服务也复用它）

用法:
  python tools/flashctl.py state
  python tools/flashctl.py eval "JSON.stringify(Object.keys(gamePublic.forAs))"
  python tools/flashctl.py key "{TAB}ACCOUNT{TAB}123456{ENTER}"
  python tools/flashctl.py click 512 330
  python tools/flashctl.py login
  python tools/flashctl.py nav https://seer.61.com/play.shtml?micro=1
  python tools/flashctl.py net            # 列出 1863/1864 连接
  python tools/flashctl.py waitgame [秒]  # 等到出现 :1864 连接
"""
import ctypes, ctypes.wintypes as wt, json, sys, time, urllib.request

API = 'http://127.0.0.1:7801'


# ---------- TCP 表（纯 ctypes，不起子进程） ----------
def tcp_connections(ports=(1863, 1864)):
    class MIB_TCPROW_OWNER_PID(ctypes.Structure):
        _fields_ = [('dwState', wt.DWORD), ('dwLocalAddr', wt.DWORD), ('dwLocalPort', wt.DWORD),
                    ('dwRemoteAddr', wt.DWORD), ('dwRemotePort', wt.DWORD), ('dwOwningPid', wt.DWORD)]

    AF_INET, TCP_TABLE_OWNER_PID_ALL = 2, 5
    size = wt.DWORD(0)
    iphlpapi = ctypes.windll.iphlpapi
    if iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0) not in (0, 122):
        return []
    buf = ctypes.create_string_buffer(size.value)
    if iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0) != 0:
        return []
    n = ctypes.cast(buf, ctypes.POINTER(wt.DWORD)).contents.value
    rows = ctypes.cast(ctypes.addressof(buf) + 4, ctypes.POINTER(MIB_TCPROW_OWNER_PID))
    out = []
    for i in range(n):
        r = rows[i]
        rport = ((r.dwRemotePort & 0xFF) << 8) | ((r.dwRemotePort >> 8) & 0xFF)
        lport = ((r.dwLocalPort & 0xFF) << 8) | ((r.dwLocalPort >> 8) & 0xFF)
        if rport in ports or lport in ports:
            ip = '.'.join(str((r.dwRemoteAddr >> s) & 0xFF) for s in (0, 8, 16, 24))
            out.append({'state': r.dwState, 'remote': '%s:%d' % (ip, rport),
                        'local_port': lport, 'pid': r.dwOwningPid})
    return out


# ---------- HTTP ----------
def post(path, payload=None, timeout=20):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get(path, timeout=10):
    with urllib.request.urlopen(API + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == 'state':
        print(json.dumps(get('/state'), ensure_ascii=False, indent=2))
    elif cmd == 'eval':
        print(json.dumps(post('/eval', {'code': sys.argv[2]}), ensure_ascii=False))
    elif cmd == 'key':
        print(json.dumps(post('/key', {'keys': sys.argv[2]}), ensure_ascii=False))
    elif cmd == 'click':
        print(json.dumps(post('/click', {'x': int(sys.argv[2]), 'y': int(sys.argv[3])}), ensure_ascii=False))
    elif cmd == 'login':
        print(json.dumps(post('/login'), ensure_ascii=False))
    elif cmd == 'nav':
        print(json.dumps(post('/nav', {'url': sys.argv[2]}), ensure_ascii=False))
    elif cmd == 'net':
        print(json.dumps(tcp_connections(), ensure_ascii=False))
    elif cmd == 'waitgame':
        limit = float(sys.argv[2]) if len(sys.argv) > 2 else 60
        t0 = time.time()
        while time.time() - t0 < limit:
            c = [x for x in tcp_connections((1864,)) if x['state'] in (2, 5)]  # SYN_SENT/ESTABLISHED? state 2=SYN_SENT
            if c:
                print(json.dumps({'ok': True, 'seconds': round(time.time() - t0, 1), 'conns': c}, ensure_ascii=False))
                return
            time.sleep(1)
        print(json.dumps({'ok': False, 'seconds': limit}, ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()