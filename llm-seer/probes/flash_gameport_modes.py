import socket, struct, json, time

INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


H = ('101.35.207.167', 1272)


def test(tag, mode, cmd=1001, body=b'', wait=4):
    s = socket.create_connection(H, timeout=4)
    t0 = time.time()
    if mode == 'policy_same':
        s.sendall(b'<policy-file-request/>\x00')
        try:
            s.settimeout(2)
            s.recv(2048)
        except Exception:
            pass
    elif mode == 'delay':
        time.sleep(0.3)
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
    dt = (time.time() - t0) * 1000
    s.close()
    print('%-26s %-8s %6.0fms recv=%d %s' % (tag, why, dt, len(out), out[:32].hex()))


def idle(tag, secs=4):
    s = socket.create_connection(H, timeout=4)
    s.settimeout(secs)
    try:
        d = s.recv(1)
        print('%-26s idle -> %s' % (tag, 'closed by server' if not d else 'got %r' % d))
    except socket.timeout:
        print('%-26s idle -> still open' % tag)
    s.close()


idle('idle no policy')
test('no policy 1001(empty)', 'direct')
test('policy same conn 1001', 'policy_same')
test('delay 300ms 1001', 'delay')
test('no policy 101', 'direct', cmd=101)
test('no policy 1001(sess)', 'direct', body=SESS + b'\x00' * 492)
test('policy same 1001(sess)', 'policy_same', body=SESS + b'\x00' * 492)