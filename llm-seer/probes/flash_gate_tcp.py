import socket, struct, json

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0, ver=b'\x31'):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def recv_all(s, wait=3):
    s.settimeout(wait)
    out = b''
    why = 'timeout'
    try:
        while len(out) < 8192:
            c = s.recv(4096)
            if not c:
                why = 'closed'; break
            out += c
    except socket.timeout:
        pass
    return out, why


def run(tag, sends, wait=3):
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    try:
        s.recv(1024)
    except Exception:
        pass
    s.close()
    s = socket.create_connection(HOST, timeout=6)
    for f in sends:
        s.sendall(f)
    data, why = recv_all(s, wait)
    s.close()
    print('%-28s %-8s recv=%d' % (tag, why, len(data)))
    p = 0
    while p + 17 <= len(data):
        ln = struct.unpack_from('>I', data, p)[0]
        if ln < 17 or p + ln > len(data):
            print('   raw tail', data[p:].hex()); break
        print('   hdr=%s uid=%s res=%s body=%s' % (
            data[p:p + 5].hex(), data[p + 9:p + 13].hex(),
            data[p + 13:p + 17].hex(), data[p + 17:p + ln].hex()))
        p += ln
    if p == 0 and data:
        print('   raw', data[:40].hex())


run('101 alone', [frame(101)])
run('109 alone (empty)', [frame(109, b'')])
run('111 alone (empty)', [frame(111, b'')])
run('109 session+u32', [frame(109, SESS + b'\x00\x00\x00\x00')])
run('111 then 109 sess', [frame(111, b''), frame(109, SESS + b'\x00\x00\x00\x00')])
run('109 then 111 then 109', [frame(109, SESS + b'\x00\x00\x00\x00'),
                              frame(111, b''),
                              frame(109, SESS + b'\x00\x00\x00\x00')], wait=4)