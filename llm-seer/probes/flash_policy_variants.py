import socket, struct, time

HOST = ('101.43.19.60', 1863)
UID = ACCOUNT


def frame(cmd, body=b'', r=0, ver=b'\x31', uid=UID):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', uid) + struct.pack('>i', r) + body)


def run(tag, payload, policy='fresh', wait=4):
    """policy=fresh: policy on separate conn then new conn; same: policy+payload on one conn; none: no policy"""
    try:
        s = socket.create_connection(HOST, timeout=6)
    except Exception as e:
        print(tag, 'connect fail', e); return
    if policy == 'fresh':
        s.sendall(b'<policy-file-request/>\x00'); s.recv(1024); s.close()
        s = socket.create_connection(HOST, timeout=6)
    elif policy == 'same':
        s.sendall(b'<policy-file-request/>\x00')
        try:
            s.recv(1024)
        except Exception:
            pass
    t0 = time.time()
    try:
        s.sendall(payload)
    except Exception as e:
        print('%-30s send fail %s' % (tag, e)); return
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
    elif out:
        d = 'raw=' + out[:24].hex()
    print('%-30s %-8s %5.0fms recv=%-4d %s' % (tag, why, dt, len(out), d))


z130 = b'\x00' * 130
run('103 no policy', frame(103, z130), policy='none')
run('101 no policy', frame(101), policy='none')
run('102 no policy', frame(102), policy='none')
run('103 policy same conn', frame(103, z130), policy='same')
run('101 policy same conn', frame(101), policy='same')
run('103 uid0 policy', frame(103, z130, uid=0))
run('103 uid0 no policy', frame(103, z130, uid=0), policy='none')