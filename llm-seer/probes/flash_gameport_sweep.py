import socket, struct, json

INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def probe(host, port, cmd, body=b'', wait=2.0):
    try:
        s = socket.create_connection((host, port), timeout=4)
    except Exception as e:
        return 'connfail', b''
    try:
        s.sendall(b'<policy-file-request/>\x00'); s.settimeout(2.5); s.recv(2048)
    except Exception:
        pass
    s.close()
    try:
        s = socket.create_connection((host, port), timeout=4)
    except Exception as e:
        return 'connfail', b''
    s.sendall(frame(cmd, body))
    s.settimeout(wait)
    out = b''; why = 'timeout'
    try:
        while True:
            c = s.recv(8192)
            if not c:
                why = 'closed'; break
            out += c
    except socket.timeout:
        pass
    s.close()
    return why, out


host, port = '101.35.207.167', 1272
cmds = list(range(100, 116)) + [200, 1000, 1001, 1002, 1003, 2000, 2001, 42494, 45963]
hits = []
for c in cmds:
    why, out = probe(host, port, c)
    if why != 'closed':
        hits.append((c, why, out[:40].hex()))
print('%s:%d empty-body non-closed: %d' % (host, port, len(hits)))
for h in hits:
    print('  cmd=%-5d %-8s %s' % h)

hits2 = []
for c in [x[0] for x in hits]:
    why, out = probe(host, port, c, SESS + b'\x00' * 4)
    if why != 'closed':
        hits2.append((c, why, out[:48].hex()))
print('with session body non-closed: %d' % len(hits2))
for h in hits2:
    print('  cmd=%-5d %-8s %s' % h)