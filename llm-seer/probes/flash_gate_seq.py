import socket, struct, json, base64, time

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])
BODY508 = bytearray(base64.b64decode(INFO['bodyB64']))
BODY508[0:16] = SESS
CHAIN = [0]


def frame(cmd, body=b'', ver=b'\x31'):
    r = 0
    if cmd > 1000:
        x = 0
        for b in body:
            x ^= b
        r = CHAIN[0] - CHAIN[0] // 3 + 113 + len(body) % 17 + cmd % 23 + x + 7
        CHAIN[0] = r
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def show(tag, data):
    if not data:
        print('   %-14s -> (nothing)' % tag); return
    p = 0
    while p + 17 <= len(data):
        ln = struct.unpack_from('>I', data, p)[0]
        if ln < 17 or p + ln > len(data):
            print('   %-14s raw %s' % (tag, data[p:p + 32].hex())); return
        print('   %-14s <= cmd=%-5d len=%-4d res=%-4d body=%s' % (
            tag, struct.unpack_from('>I', data, p + 5)[0], ln,
            struct.unpack_from('>i', data, p + 13)[0], data[p + 17:p + min(ln, 49)].hex()))
        p += ln


def run(tag, steps, wait=3):
    CHAIN[0] = 0
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    try:
        s.recv(1024)
    except Exception:
        pass
    s.close()
    s = socket.create_connection(HOST, timeout=6)
    print(tag)
    for name, f in steps:
        try:
            s.sendall(f)
        except Exception as e:
            print('   %-14s send fail %s' % (name, e)); return
        s.settimeout(wait)
        out = b''; why = 'ok'
        try:
            while len(out) < 8192:
                c = s.recv(4096)
                if not c:
                    why = 'closed'; break
                out += c
                break  # one read is enough here
        except socket.timeout:
            why = 'timeout'
        if why == 'closed':
            print('   %-14s -> closed' % name)
            s.close(); return
        show(name, out)
    s.close()


run('[1] 105(sess) alone', [('105', frame(105, SESS + b'\x00' * 4))])
run('[2] 105sess -> 111 -> 109sess', [
    ('105', frame(105, SESS + b'\x00' * 4)),
    ('111', frame(111)),
    ('109', frame(109, SESS + b'\x00' * 4))])
run('[3] 111 -> 109sess -> 1001', [
    ('111', frame(111)),
    ('109', frame(109, SESS + b'\x00' * 4)),
    ('1001', frame(1001, bytes(BODY508)))])
run('[4] 105sess ->111->109->1001', [
    ('105', frame(105, SESS + b'\x00' * 4)),
    ('111', frame(111)),
    ('109', frame(109, SESS + b'\x00' * 4)),
    ('1001', frame(1001, bytes(BODY508)))])