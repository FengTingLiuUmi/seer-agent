import json, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print('[1] prep session ...')
subprocess.run(['node', 'tools/prep_pwd.mjs'], cwd=ROOT, capture_output=True, text=True)
j = json.load(open(os.path.join(ROOT, 'login.json'), encoding='utf-8'))
sid = '%d' % j['uid'] + j['sessionHex']
print('    sid =', sid)

url = 'https://seer.61.com/play.shtml?micro=1&uid=%d&sid=%s' % (j['uid'], sid)
print('[2] nav ->', url)
print('   ', flashctl.post('/nav', {'url': url}))

print('[3] wait for :1864 ...')
t0 = time.time()
while time.time() - t0 < 45:
    conns = [c for c in flashctl.tcp_connections() if c['remote'].endswith(':1864')]
    if conns:
        print('    GAME CONNECTED', json.dumps(conns, ensure_ascii=False), 'after', round(time.time()-t0,1), 's')
        break
    time.sleep(1.5)
else:
    print('    no :1864 connection in 45s')

st = flashctl.get('/state')
print('[4] state:', json.dumps(st, ensure_ascii=False)[:300])