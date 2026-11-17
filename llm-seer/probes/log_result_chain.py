import json, base64, struct, sys
from collections import defaultdict

path = r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\relogin4.jsonl'
frames = []
for line in open(path, encoding='utf-8'):
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get('kind') not in ('C2S', 'S2C'):
        continue
    raw = base64.b64decode(o['b64'])
    ln = struct.unpack_from('>I', raw, 0)[0]
    ver = raw[4]
    cmd = struct.unpack_from('>I', raw, 5)[0]
    uid = struct.unpack_from('>I', raw, 9)[0]
    res = struct.unpack_from('>i', raw, 13)[0]
    frames.append({'t': o['t'], 'k': o['kind'], 'ws': o.get('ws'), 'cmd': cmd,
                   'uid': uid, 'res': res, 'ver': ver, 'body': raw[17:], 'len': ln})

lastws = frames[-1]['ws']
sess = [f for f in frames if f['ws'] == lastws]
print('session', lastws, 'frames', len(sess))

def formula(r, body, cmd):
    x = 0
    for b in body:
        x ^= b
    return r - r // 3 + 113 + len(body) % 17 + cmd % 23 + x + 7

# hypothesis A: r = last C2S computed result
rA = 0
# hypothesis B: r = last frame's result (any direction)
rB = 0
# hypothesis C: r = last S2C result
rC = 0
okA = okB = okC = 0
tot = 0
for f in sess:
    if f['k'] == 'C2S' and f['cmd'] > 1000:
        tot += 1
        pA = formula(rA, f['body'], f['cmd'])
        pB = formula(rB, f['body'], f['cmd'])
        pC = formula(rC, f['body'], f['cmd'])
        if pA == f['res']: okA += 1
        if pB == f['res']: okB += 1
        if pC == f['res']: okC += 1
        rA = pA
        rC = f['res']
    rB = f['res'] if f['res'] else rB
print('C2S cmd>1000 frames:', tot, 'matchA(last c2s)', okA, 'matchB(any)', okB, 'matchC(last s2c)', okC)

print('\nfirst 20 frames of session:')
for f in sess[:20]:
    print('  %-3s cmd=%-6d len=%-4d res=%-6d body=%s' % (
        f['k'], f['cmd'], f['len'], f['res'], f['body'][:16].hex()))