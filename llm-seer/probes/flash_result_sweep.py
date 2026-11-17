import socket, struct, time

HOST = ('101.43.19.60', 1863)
UID = ACCOUNT


def frame(cmd, body=b'', r=0, ver=b'\x31', uid=UID):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', uid) + struct.pack('>i', r) + body)


def conn(host):
    s = socket.create_connection(host, timeout=6)
    try:
        s.sendall(b'<policy-file-request/>\x00'); s.recv(1024)
    except Exception:
        pass
    s.close()
    return socket.create_connection(host, timeout=6)


def run(tag, payload, wait=4):
    s = conn(HOST)
    t0 = time.time()
    s.sendall(payload)
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
    dt = (time.time() - t0) * 1000
    s.close()
    d = ''
    if len(out) >= 17:
        d = 'cmd=%d res=%d body=%s' % (struct.unpack_from('>I', out, 5)[0],
                                       struct.unpack_from('>i', out, 13)[0],
                                       out[17:17 + min(16, len(out) - 17)].hex())
    print('%-24s %-8s %5.0fms recv=%-4d %s' % (tag, why, dt, len(out), d))


z130 = b'\x00' * 130
for r in (0, 1, 7, 113, 120, 133, 142, 250, -1, 1000):
    run('103 zeros r=%d' % r, frame(103, z130, r=r))

for ver in (0x00, 0x01, 0x0a, 0x0e, 0x0f, 0x10, 0x30, 0x32, 0x33, 0x41):
    run('103 ver=%02x' % ver, frame(103, z130, ver=bytes([ver])))

for r in (0, 133, 132):
    run('1002 r=%d' % r, frame(1002, b'', r=r))