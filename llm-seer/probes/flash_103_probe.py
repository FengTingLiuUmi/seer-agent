import socket, struct, hashlib, sys, re, time

HOSTS = [('101.43.19.60', 1863), ('111.229.85.11', 1863), ('124.220.171.66', 1863)]
UID = ACCOUNT


def password():
    txt = open(r'F:\seer\account.ini', 'r', encoding='utf-8', errors='ignore').read()
    m = re.search(r'\[ACCOUNT\]\s*\n\s*pass\s*=\s*(\S+)', txt)
    return m.group(1) if m else None


PWD = password()


def pad(b, n):
    return b[:n] + b'\x00' * (n - len(b))


STATE = [0]


def frame(cmd, body=b'', ver=b'\x31'):
    total = 17 + len(body)
    r = 0
    if cmd > 1000:
        x = 0
        for b in body:
            x ^= b
        r = STATE[0] - STATE[0] // 3 + 113 + len(body) % 17 + cmd % 23 + x + 7
        STATE[0] = r
    return (struct.pack('>I', total) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def body103(pwd32):
    b = pad(pwd32, 32)
    b += struct.pack('>I', 0)      # tmcid
    b += struct.pack('>I', 2)      # GAME_TYPE
    b += struct.pack('>I', 0)
    b += b'\x00' * 16              # IGM_ID
    b += b'\x00' * 6               # IMG_BY
    b += pad(b'0', 64)             # getTopLeftTmcid()
    return b


def dmd5(p):
    return hashlib.md5(hashlib.md5(p.encode()).hexdigest().encode()).hexdigest().encode()


def recv_all(s, t=6.0):
    s.settimeout(t)
    out = b''
    try:
        while len(out) < 8192:
            c = s.recv(4096)
            if not c:
                return out, 'closed'
            out += c
    except socket.timeout:
        return out, 'timeout'
    return out, 'capped'


def show(tag, data, why):
    if not data:
        print('%-22s -> no data (%s)' % (tag, why))
        return
    if len(data) >= 17:
        ln, cmd, uid, res = struct.unpack_from('>I', data, 0)[0], struct.unpack_from('>I', data, 5)[0], \
            struct.unpack_from('>I', data, 9)[0], struct.unpack_from('>i', data, 13)[0]
        print('%-22s -> %s | len=%d cmd=%d uid=%d res=%d body=%s' % (
            tag, why, ln, cmd, uid, res, data[17:17 + min(24, len(data) - 17)].hex()))
    else:
        print('%-22s -> %s raw=%s' % (tag, why, data[:32].hex()))


def connect(host):
    s = socket.create_connection(host, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    pol = s.recv(1024, socket.MSG_PEEK) if False else s.recv(1024)
    s.close()
    s = socket.create_connection(host, timeout=6)
    return s, pol


host = HOSTS[0]
print('pwd loaded:', bool(PWD))

# baseline: 101
s, pol = connect(host)
print('policy', len(pol), pol[:40])
s.sendall(frame(101))
show('101', *recv_all(s, 5))
s.close()

# 103 wrong password (double md5)
s, pol = connect(host)
s.sendall(frame(103, body103(dmd5('wrongpw_123'))))
show('103 wrongpwd dmd5', *recv_all(s, 8))
s.close()

# 103 real password (double md5)
s, pol = connect(host)
s.sendall(frame(103, body103(PWD and dmd5(PWD) or dmd5('x'))))
show('103 realpwd dmd5', *recv_all(s, 8))
s.close()

# 103 single md5 (old format) for comparison, 130B
s, pol = connect(host)
s.sendall(frame(103, body103(hashlib.md5(b'123456').hexdigest().encode())))
show('103 singlemd5 130B', *recv_all(s, 8))
s.close()

# A: 105/109/111 empty body on one connection
s, pol = connect(host)
for cmd in (105, 109, 111):
    STATE[0] = 0
    s.sendall(frame(cmd, b''))
    d, why = recv_all(s, 3)
    show('solo %d' % cmd, d, why)
s.close()