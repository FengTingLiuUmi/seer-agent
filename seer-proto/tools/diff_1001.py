import base64, json, sys

# 官方抓包里的 c2s 1001
off = None
for line in open('seer-auto/relogin4.jsonl', encoding='utf-8'):
    e = json.loads(line)
    if e.get('kind') == 'C2S' and e.get('cmd') == 1001:
        off = base64.b64decode(e['b64'])[17:]
        break
if off is None:
    print('no official 1001'); sys.exit(1)

# 我们最近一次 c2s 1001
ours = None
try:
    for line in open('seer-proto/session.jsonl', encoding='utf-8'):
        e = json.loads(line)
        if e.get('dir') == 'c2s' and e.get('cmd') == 1001:
            ours = bytes.fromhex(e['body'])
            break
except FileNotFoundError:
    pass

print('official len', len(off), 'ours len', len(ours) if ours else None)
if ours:
    n = min(len(off), len(ours))
    diffs = [(i, off[i], ours[i]) for i in range(n) if off[i] != ours[i]]
    print('diff bytes', len(diffs))
    for i, a, b in diffs[:24]:
        print('  off 0x%03x: official=%02x ours=%02x' % (i, a, b))
    # 打印官方 body 头部 u32
    u = [int.from_bytes(off[i:i+4], 'big') for i in range(0, 64, 4)]
    print('official u32 head', u)
    if ours:
        u2 = [int.from_bytes(ours[i:i+4], 'big') for i in range(0, 64, 4)]
        print('ours     u32 head', u2)