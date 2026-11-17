import socket, json, time

s = socket.create_connection(('127.0.0.1', 7802), timeout=60)
buf = b''


def read_line(t=20):
    global buf
    s.settimeout(t)
    while b'\n' not in buf:
        c = s.recv(65536)
        if not c:
            return None
        buf += c
    line, buf = buf.split(b'\n', 1)
    return json.loads(line)


def send(obj):
    s.sendall((json.dumps(obj) + '\n').encode())


# 绛?ready
deadline = time.time() + 25
ready = False
while time.time() < deadline:
    m = read_line(5)
    if not m:
        break
    if m['type'] == 'ready':
        ready = True
        print('ready')
        break
    print('  <', m['type'], m.get('cmd'), m.get('name', ''), 'len=%s' % m.get('len'))
if not ready:
    raise SystemExit('no ready')

queries = [3401, 47334, 4178, 1105, 3454, 3401]
for qid, cmd in enumerate(queries, 1):
    send({'id': qid, 'cmd': cmd})
    got = []
    t0 = time.time()
    while time.time() - t0 < 4:
        try:
            m = read_line(1.5)
        except socket.timeout:
            break
        if not m:
            break
        if m['type'] == 'c2s' and m.get('id') == qid:
            print('c2s %-6d %-22s res=%d' % (m['cmd'], m.get('name', ''), m['res']))
            continue
        if m['type'] in ('s2c',):
            got.append(m)
            if m['cmd'] == cmd:
                print('  s2c %-6d %-22s len=%-4d body=%s' % (m['cmd'], m.get('name', ''), m['len'], m['bodyHex'][:40]))
                break
print('done')
s.close()
