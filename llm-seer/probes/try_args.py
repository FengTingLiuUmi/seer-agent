#!/usr/bin/env python3
"""逐个尝试 GET_PET_LIST(2303) / GET_DAILY_VALUE(2707) 的参数形态。
每次尝试 = 一次重新登录（避免同 session 复用），失败会立刻 EOF。
"""
import json, os, subprocess, sys, time

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UIDHEX = '048f04a9'

CANDIDATES = [
    (2303, 'start0', '00000000'),
    (2303, 'start0count8', '0000000000000008'),
    (2303, 'uid', UIDHEX),
    (2707, 'zero', '00000000'),
    (2707, 'uid', UIDHEX),
]


def run(cmd, outfile):
    with open(outfile, 'wb') as f:
        p = subprocess.run(cmd, cwd=PROTO, stdout=f, stderr=subprocess.STDOUT)
    return p.returncode


def prep():
    run(['node', r'tools\prep_token.mjs'], '_prep.log')
    txt = open(os.path.join(PROTO, '_prep.log'), encoding='utf-8', errors='replace').read()
    if 'ok uid=' not in txt:
        return False
    return True


def try_one(cmd, tag, bodyhex):
    steps = [
        {"cmd": 42494, "delayMs": 0},
        {"cmd": 1002, "delayMs": 150},
        {"cmd": 1016, "bodyHex": "00000002", "delayMs": 300},
        {"cmd": cmd, "bodyHex": bodyhex, "delayMs": 800},
    ]
    sp = os.path.join(PROTO, '_steps_try.json')
    json.dump(steps, open(sp, 'w'))
    log = os.path.join(PROTO, '_try.log')
    run(['.\\seerproto.exe', '-info', 'login.json', '-steps', sp, '-seconds', '10', '-hex'], log)
    txt = open(log, encoding='utf-8', errors='replace').read()
    ok = ('S2C cmd=%d ' % cmd) in txt
    kicked = 'read err: EOF' in txt
    tail = ''
    for ln in txt.splitlines():
        if 'S2C cmd=%d ' % cmd in ln or 'read err' in ln or '>>> C2S %d' % cmd in ln:
            tail = ln.strip()[:120]
    return ok, kicked, tail


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for cmd, tag, body in CANDIDATES:
        if only and str(cmd) != only:
            continue
        if not prep():
            print('%s %s: prep 失败，跳过' % (cmd, tag))
            time.sleep(5)
            continue
        ok, kicked, tail = try_one(cmd, tag, body)
        print('%-6d %-12s %-5s kicked=%-5s | %s' % (cmd, tag, 'OK' if ok else 'no', kicked, tail))
        sys.stdout.flush()
        time.sleep(12)