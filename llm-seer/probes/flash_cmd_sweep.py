import socket, struct, time

HOST = ('101.43.19.60', 1863)
UID = ACCOUNT


def frame(cmd, body=b'', r=0, ver=b'\x31'):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def probe(cmd, body=b'', wait=2.5):
    s = socket.create_connection(HOST, timeout=6)
    try:
        s.sendall(b'<policy-file-request/>\x00'); s.recv(1024)
    except Exception:
        pass
    s.close()
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(frame(cmd, body))
    s.settimeout(wait)
    out = b''; why = 'timeout'
    try:
        while len(out) < 4096:
            c = s.recv(4096)
            if not c:
                why = 'closed'; break
            out += c
    except socket.timeout:
        pass
    s.close()
    return why, out


cmds = list(range(0, 21)) + [100, 102, 103, 105, 106, 109, 111, 1000, 1001, 1002,
                             2001, 42494, 45963, 45962, 63003]
other = []
for c in cmds:
    try:
        why, out = probe(c)
    except Exception as e:
        print('cmd %-6d conn fail %s' % (c, e)); continue
    tag = why
    if out:
        tag += ':' + out[:17].hex()
    if why != 'closed':
        other.append((c, why, len(out), out[:24].hex()))
print('tested', len(cmds), 'cmds; non-closed:', len(other))
for o in other:
    print('  cmd=%-6d %-8s recv=%-3d %s' % o)