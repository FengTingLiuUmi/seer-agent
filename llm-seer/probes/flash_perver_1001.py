import socket, struct, json, base64, time

INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])
BODY = bytearray(base64.b64decode(INFO['bodyB64']))
BODY[0:16] = SESS
CHAIN = [0]


def frame(cmd, body=b'', r=None):
    if r is None:
        r = 0
        if cmd > 1000:
            x = 0
            for b in body:
                x ^= b
            r = CHAIN[0] - CHAIN[0] // 3 + 113 + len(body) % 17 + cmd % 23 + x + 7
            CHAIN[0] = r
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def run(tag, host, port, sends, wait=6):
    try:
        s = socket.create_connection((host, port), timeout=5)
    except Exception as e:
        print('%-30s connect fail %s' % (tag, e)); return
    try:
        s.sendall(b'<policy-file-request/>\x00'); s.settimeout(3); s.recv(2048)
    except Exception:
        pass
    s.close()
    s = socket.create_connection((host, port), timeout=5)
    CHAIN[0] = 0
    for f in sends:
        s.sendall(f)
    s.settimeout(wait)
    out = b''; why = 'timeout'
    try:
        while len(out) < 65536:
            c = s.recv(8192)
            if not c:
                why = 'closed'; break
            out += c
    except socket.timeout:
        pass
    s.close()
    print('%-30s %-8s recv=%d' % (tag, why, len(out)))
    p = 0
    while p + 17 <= len(out):
        ln = struct.unpack_from('>I', out, p)[0]
        if ln < 17 or p + ln > len(out):
            print('   raw', out[p:p + 32].hex()); break
        print('   <= cmd=%-5d len=%-5d res=%-5d body=%s' % (
            struct.unpack_from('>I', out, p + 5)[0], ln,
            struct.unpack_from('>i', out, p + 13)[0], out[p + 17:p + min(ln, 41)].hex()))
        p += ln


H = [('101.43.19.60', 1219), ('101.35.207.167', 1272)]
for h, p in H:
    run('%s:%d 1001(sess)' % (h, p), h, p, [frame(1001, bytes(BODY))])
for h, p in H:
    run('%s:%d 1001(zeros)' % (h, p), h, p, [frame(1001, bytes(508))])