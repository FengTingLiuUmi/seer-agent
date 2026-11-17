#!/usr/bin/env python3
"""无人值守命令探测器：自动重登 + 冷却退避 + 结果落盘

用法:
  python tools/probe_cmds.py 2303:0000000100000014 2415
  python tools/probe_cmds.py --gap 30 --cooldown 300 --retry 3 2303:0000000100000014
  python tools/probe_cmds.py --status          # 只看已有结果

规则（很重要）:
  * 一次登录只能探一条命令（session 一次性 + 错帧即断线）
  * 没有 S2C 1001/2001 = 服务器冷却 → 等 cooldown 秒后重试，最多 retry 次
  * 结果写 tools/probe_results.json（含每次尝试、时间戳）
"""
import json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'seerproto.exe')
STEPS = os.path.join(ROOT, 'steps_probe.json')
LOG = os.path.join(ROOT, 'session.jsonl')
RES = os.path.join(ROOT, 'tools', 'probe_results.json')
NAMES = {int(v): k for k, v in json.load(open(os.path.join(ROOT, 'data', 'commandid.json'), encoding='utf-8')).items()}


def log(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


def decode_text(hexs):
    try:
        b = bytes.fromhex(hexs or '')
    except Exception:
        return ''
    u = b.decode('utf-8', 'ignore')
    return ''.join(c for c in u if c.isprintable())[:200]


def do_login():
    p = subprocess.run(['node', 'tools/prep_pwd.mjs'], cwd=ROOT, capture_output=True, text=True)
    out = (p.stdout or '') + (p.stderr or '')
    return 'ok uid=' in out or ('session=' in out and 'gate=' in out), out.strip().splitlines()[-1][:120] if out.strip() else ''


def probe_once(cmd, body_hex, seconds):
    open(STEPS, 'w', encoding='utf-8').write(json.dumps([{'cmd': cmd, 'bodyHex': body_hex, 'delayMs': 600}]))
    for f in (LOG, os.path.join(ROOT, '.seerproto.lock')):
        try:
            os.remove(f)
        except OSError:
            pass
    p = subprocess.run([EXE, '-info', 'login.json', '-steps', 'steps_probe.json', '-seconds', str(seconds)],
                       cwd=ROOT, capture_output=True, text=True, timeout=seconds + 40)
    out = (p.stdout or '') + (p.stderr or '')
    ev = []
    if os.path.exists(LOG):
        for line in open(LOG, encoding='utf-8'):
            try:
                ev.append(json.loads(line))
            except Exception:
                pass
    got1001 = any(e.get('dir') == 's2c' and e.get('cmd') == 1001 for e in ev)
    world = any(e.get('cmd') == 2001 for e in ev)
    reply = [e for e in ev if e.get('dir') == 's2c' and e.get('cmd') == cmd]
    body = (reply[0].get('body') or '') if reply else ''
    return {'cmd': cmd, 'name': NAMES.get(cmd, ''), 'body_in': body_hex,
            'got1001': got1001, 'world': world,
            'sent': any(e.get('dir') == 'c2s' and e.get('cmd') == cmd for e in ev),
            'reply': len(reply), 'reply_len': (reply[0].get('len') if reply else 0),
            'msg': (reply[0].get('msg') if reply else '') or '',
            'body': body, 'text': decode_text(body),
            'eof': 'read err' in out, 'ts': time.strftime('%Y-%m-%d %H:%M:%S')}


def probe_with_recovery(cmd, body_hex, seconds, cooldown, retry):
    attempts = []
    for i in range(1, retry + 1):
        log('probe %d body=%s (attempt %d/%d)' % (cmd, body_hex or '(empty)', i, retry))
        ok, info = do_login()
        if not ok:
            log('login step failed: %s' % info)
        r = probe_once(cmd, body_hex, seconds)
        attempts.append(r)
        if r['world'] and r['sent']:
            tag = 'REPLY' if r['reply'] else ('CLOSED' if r['eof'] else 'NO-REPLY')
            log('  -> %s reply=%d len=%d %s' % (tag, r['reply'], r['reply_len'], (r['text'] or r['msg'])[:60]))
            r['attempts_count'] = len(attempts)
            return r
        if not r['world']:
            log('  -> no 2001 (server cooldown?)')
            if i < retry:
                log('  sleeping %ds before retry' % cooldown)
                time.sleep(cooldown)
            continue
        # world but command not sent (shouldn't happen) → 继续
        if i < retry:
            time.sleep(cooldown)
    attempts[-1]['attempts_count'] = len(attempts)
    return attempts[-1]


def main():
    argv = sys.argv[1:]
    gap, cooldown, retry, seconds = 30, 300, 3, 18
    while argv and argv[0].startswith('--'):
        k = argv[0]
        if k == '--status':
            data = json.load(open(RES, encoding='utf-8')) if os.path.exists(RES) else []
            for r in data:
                print('%-6s %-26s reply=%d len=%d %s  %s' % (
                    r['cmd'], r['name'][:26], r['reply'], r['reply_len'], (r['text'] or '')[:40], r.get('ts', '')))
            return
        v = int(argv[1]); argv = argv[2:]
        if k == '--gap':
            gap = v
        elif k == '--cooldown':
            cooldown = v
        elif k == '--retry':
            retry = v
        elif k == '--seconds':
            seconds = v
    specs = []
    for a in argv:
        if ':' in a:
            c, b = a.split(':', 1)
            specs.append((int(c), b))
        else:
            specs.append((int(a), ''))
    if not specs:
        print(__doc__)
        return
    results = json.load(open(RES, encoding='utf-8')) if os.path.exists(RES) else []
    for i, (cmd, body) in enumerate(specs):
        if i:
            log('gap %ds' % gap)
            time.sleep(gap)
        r = probe_with_recovery(cmd, body, seconds, cooldown, retry)
        results.append(r)
        save = [{k: v for k, v in x.items() if k != 'attempts'} for x in results]
        open(RES, 'w', encoding='utf-8').write(json.dumps(save, ensure_ascii=False, indent=1))
    print('\n==== summary ====')
    for r in results[-len(specs):]:
        tag = 'REPLY' if r['reply'] else ('CLOSED' if r['eof'] else 'NO-REPLY')
        print('%-8s %-26s world=%s reply=%d len=%d %s' % (
            tag, r['name'][:26], r['world'], r['reply'], r['reply_len'], (r['text'] or r['msg'])[:50]))


if __name__ == '__main__':
    main()