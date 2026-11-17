import json, base64, struct, collections

CMDS = json.load(open(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\commandid.json', encoding='utf-8'))
NAME = {v: k for k, v in CMDS.items()}
path = r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\relogin4.jsonl'

F = []
for line in open(path, encoding='utf-8'):
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get('kind') not in ('C2S', 'S2C'):
        continue
    raw = base64.b64decode(o['b64'])
    F.append({'k': o['kind'], 't': o['t'], 'ws': o.get('ws'),
              'cmd': struct.unpack_from('>I', raw, 5)[0],
              'res': struct.unpack_from('>i', raw, 13)[0],
              'body': raw[17:]})

ws = F[-1]['ws']
S = [f for f in F if f['ws'] == ws]
# 从第一次 2001 开始
start = next(i for i, f in enumerate(S) if f['k'] == 'S2C' and f['cmd'] == 2001)
print('ws', ws, 'frames from 2001:', len(S) - start)
print('--- C2S 顺序（前 40 条）---')
n = 0
for f in S[start:]:
    if f['k'] == 'C2S':
        print('  %-6d %-22s res=%-5d body=%s' % (f['cmd'], NAME.get(f['cmd'], '?'), f['res'], f['body'][:24].hex()))
        n += 1
        if n >= 40:
            break

print('--- C2S 命令计数（整段会话）---')
c = collections.Counter(f['cmd'] for f in S if f['k'] == 'C2S')
for cmd, cnt in c.most_common(15):
    print('  %-6d %-22s x%d' % (cmd, NAME.get(cmd, '?'), cnt))