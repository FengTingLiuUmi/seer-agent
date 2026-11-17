"""干净重试：等到冷却窗口 → 登录 → 取精灵列表 → 打印结果。

冷却策略：上一次登录是 17:54，等到 18:12 之后（≥18 分钟）再试。
失败则每 10 分钟重试，最多 3 次（避免把账号继续顶进冷却）。
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICE = 'http://127.0.0.1:7820'
EARLIEST = dt.datetime(2026, 11, 13, 18, 26, 0)


def post(path, body=None, timeout=240):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(SERVICE + path, data=data, method='POST',
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def log(msg):
    print(dt.datetime.now().strftime('%H:%M:%S') + ' ' + msg, flush=True)


def wait_until(t):
    while dt.datetime.now() < t:
        remain = (t - dt.datetime.now()).total_seconds()
        time.sleep(min(60, max(5, remain)))
    return True


def attempt(n):
    boot = 'ack' if n >= 2 else None
    log('attempt %d: login (boot=%s)' % (n, boot))
    t0 = time.time()
    body = {'boot': boot} if boot else {}
    r = post('/api/login', body)
    log('  ok=%s ready=%s elapsed=%ss dead=%s' % (r.get('ok'), r.get('ready'),
                                                  r.get('elapsed'), r.get('dead_reason')))
    st = r.get('state') or {}
    mp = st.get('map') or {}
    log('  map=%r nick=%r' % (mp.get('map_name'), mp.get('nick')))
    if not r.get('ok'):
        tail = (r.get('proto_out') or '').splitlines()[-4:]
        for ln in tail:
            log('  | ' + ln[:160])
        return False
    log('  READY in %.1fs' % (time.time() - t0))
    # 取精灵列表
    rp = post('/api/pets', {'waitMs': 8000})
    log('  pets ok=%s rawLen=%s' % (rp.get('ok'), rp.get('rawLen')))
    if rp.get('ok'):
        path = os.path.join(ROOT, 'bodies', '2303.bin')
        log('  saved %s' % path)
        # 也取一次地图玩家与成就，确认通道
        for cmd in (2003, 3401):
            rr = post('/api/send', {'cmd': cmd, 'waitMs': 5000})
            fr = (rr.get('frames') or [{}])[0]
            log('  cmd=%s -> len=%s res=%s' % (cmd, fr.get('len'), fr.get('res')))
        return True
    return False


def main():
    log('waiting for cooldown window %s' % EARLIEST.strftime('%H:%M'))
    wait_until(EARLIEST)
    for i in range(1, 4):
        try:
            if attempt(i):
                log('SUCCESS')
                return 0
        except Exception as e:
            log('  exception: %s' % e)
        nxt = dt.datetime.now() + dt.timedelta(minutes=10)
        log('  retry after %s' % nxt.strftime('%H:%M'))
        wait_until(nxt)
    log('FAILED after retries')
    return 1


if __name__ == '__main__':
    sys.exit(main())