import socket, struct, json, base64, hashlib, time

INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESSION = bytes.fromhex(INFO['sessionHex'])
BODY508 = bytearray(base64.b64decode(INFO['bodyB64']))
BODY508[0:16] = SESSION

HOSTS = [('101.43.19.60', 1863), ('101.43.19.60', 1864),
         ('111.229.85.11', 1863), ('111.229.85.11', 1864),
         ('124.220.171.66', 1863), ('124.220.171.66', 1864)]


def frame(cmd, body=b'', ver=b'\x31', chain=None):
    total = 17 + len(body)
    r = 0
    if chain is not None:
        x = 0
        for b in body:
            x ^= b
        r = chain[0] - chain[0] // 3 + 113 + len(body) % 17 + cmd % 23 + x + 7
        chain[0] = r
    return (struct.pack('>I', total) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def run(host, cmd, body, wait=10, chain=None):
    tag = '%s:%d cmd=%d' % (host[0], host[1], cmd)
    s = socket.create_connection(host, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    try:
        s.recv(1024)
    except Exception:
        pass
    s.close()
    s = socket.create_connection(host, timeout=6)
    t0 = time.time()
    s.sendall(frame(cmd, body, chain=chain))
    s.settimeout(wait)
    out = b''
    why = 'timeout'
    try:
        while len(out) < 65536:
            c = s.recv(8192)
            if not c:
                why = 'closed'
                break
            out += c
    except socket.timeout:
        pass
    s.close()
    dt = (time.time() - t0) * 1000
    print('%-24s %-8s %6.0fms recv=%d' % (tag, why, dt, len(out)))
    p = 0
    n = 0
    while p + 17 <= len(out) and n < 6:
        ln = struct.unpack_from('>I', out, p)[0]
        if ln < 17 or p + ln > len(out):
            print('    bad frame len=%d at %d' % (ln, p))
            break
        c2 = struct.unpack_from('>I', out, p + 5)[0]
        res = struct.unpack_from('>i', out, p + 13)[0]
        print('    S2C cmd=%d len=%d res=%d body=%s' % (c2, ln, res, out[p + 17:p + 17 + min(24, ln - 17)].hex()))
        p += ln
        n += 1


for h in HOSTS:
    run(h, 1001, bytes(BODY508), chain=[0])

print('--- 同会话再试 101 / 102（确认通道活着） ---')
run(HOSTS[1], 101, b'')