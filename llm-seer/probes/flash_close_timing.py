import socket, struct, time

HOST = ('101.43.19.60', 1863)
UID = ACCOUNT


def frame(cmd, body=b'', ver=b'\x31', r=0, total=None, uid=UID):
    return (struct.pack('>I', 17 + len(body) if total is None else total) + ver +
            struct.pack('>I', cmd) + struct.pack('>I', uid) + struct.pack('>i', r) + body)


def conn():
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    s.recv(1024)
    s.close()
    return socket.create_connection(HOST, timeout=6)


def run(tag, payload, wait=6):
    s = conn()
    t0 = time.time()
    s.sendall(payload)
    s.settimeout(wait)
    out = b''
    why = 'timeout'
    try:
        while True:
            c = s.recv(4096)
            if not c:
                why = 'closed'
                break
            out += c
            if len(out) > 1024:
                break
    except socket.timeout:
        pass
    dt = (time.time() - t0) * 1000
    s.close()
    d = ''
    if len(out) >= 17:
        d = 'cmd=%d res=%d body=%s' % (struct.unpack_from('>I', out, 5)[0],
                                       struct.unpack_from('>i', out, 13)[0],
                                       out[17:17 + min(12, len(out) - 17)].hex())
    print('%-24s %-8s %6.0fms %s' % (tag, why, dt, d))


z130 = b'\x00' * 130
run('101 baseline', frame(101))
run('102 baseline', frame(102))
run('102 body8', frame(102, b'\x00' * 8))
run('103 zeros130', frame(103, z130))
run('106', frame(106))
run('9999 unknown', frame(9999))
run('103 badlen', frame(103, z130, total=999))
run('103 short17', frame(103, b''))
run('101 uid0', frame(101, uid=0))
run('101 ver0', frame(101, ver=b'\x00'))