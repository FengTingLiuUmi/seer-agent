import socket, struct

HOST = ('101.43.19.60', 1863)
UID = ACCOUNT


def frame(cmd, body=b'', ver=b'\x31', r=0):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def conn():
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    s.recv(1024)
    s.close()
    return socket.create_connection(HOST, timeout=6)


def probe(tag, sends, wait=5):
    s = conn()
    for f in sends:
        s.sendall(f)
    s.settimeout(wait)
    out = b''
    why = 'timeout'
    try:
        while len(out) < 4096:
            c = s.recv(4096)
            if not c:
                why = 'closed'
                break
            out += c
    except socket.timeout:
        pass
    s.close()
    if not out:
        print('%-26s -> %s' % (tag, why))
        return
    ln, cmd, uid, res = struct.unpack_from('>Ii', out, 0)[0], 0, 0, 0
    cmd = struct.unpack_from('>I', out, 5)[0]
    uid = struct.unpack_from('>I', out, 9)[0]
    res = struct.unpack_from('>i', out, 13)[0]
    print('%-26s -> %-8s len=%d cmd=%d uid=%d res=%d body=%s' % (
        tag, why, ln, cmd, uid, res, out[17:17 + min(20, len(out) - 17)].hex()))


zero130 = b'\x00' * 130

probe('102 SYSTEM_TIME', [frame(102)])
probe('106 RANGE_ONLINE', [frame(106)])
probe('105', [frame(105)])
probe('1001 LOGIN_IN', [frame(1001, b'')])
probe('1002 SYSTEM_TIME', [frame(1002, b'', r=142)])
probe('103 zeros130', [frame(103, zero130)])
probe('101 then 103 zeros', [frame(101), frame(103, zero130)])
probe('103 ver=0x00', [frame(103, zero130, ver=b'\x00')])
probe('103 uid=0', [frame(103, zero130)])
probe('103 eof-only 17B', [frame(103, b'')])