import socket, struct, hashlib, re, time

UID = ACCOUNT
HOSTS = [('101.43.19.60', 1864), ('111.229.85.11', 1864), ('124.220.171.66', 1864),
         ('101.43.19.60', 1863)]


def frame(cmd, body=b'', ver=b'\x31', r=0, uid=UID):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', uid) + struct.pack('>i', r) + body)


def conn(h, do_policy=True):
    s = socket.create_connection(h, timeout=6)
    if do_policy:
        try:
            s.sendall(b'<policy-file-request/>\x00')
            s.recv(1024)
        except Exception:
            pass
        s.close()
        s = socket.create_connection(h, timeout=6)
    return s


def run(tag, host, payloads, wait=5):
    try:
        s = conn(host)
    except Exception as e:
        print('%-30s -> connect fail %s' % (tag, e)); return
    t0 = time.time()
    for p in payloads:
        s.sendall(p)
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
    print('%-30s %-8s %6.0fms recv=%d %s' % (tag, why, dt, len(out), d))


def pw():
    t = open(r'F:\seer\account.ini', encoding='utf-8', errors='ignore').read()
    m = re.search(r'\[ACCOUNT\]\s*\n\s*pass\s*=\s*(\S+)', t)
    return m.group(1)


def dmd5(p):
    return hashlib.md5(hashlib.md5(p.encode()).hexdigest().encode()).hexdigest().encode()


def b103(p32=b'', tmcid=0):
    return (p32.ljust(32, b'\x00') + struct.pack('>I', tmcid) + b'\x00\x00\x00\x02' +
            b'\x00\x00\x00\x00' + b'\x00' * 16 + b'\x00' * 6 + b'0'.ljust(64, b'\x00'))


for h in HOSTS:
    tag = '%s:%d' % h
    run(tag + ' 101', h, [frame(101)])
    run(tag + ' 103 zeros', h, [frame(103, b'\x00' * 130)])
    run(tag + ' 103 real', h, [frame(103, b103(dmd5(pw())))])
    run(tag + ' 103 real uid0', h, [frame(103, b103(dmd5(pw())), uid=0)])
    run(tag + ' 102', h, [frame(102)])