import socket, struct, json, hashlib, re

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])
ini = open(r'F:\seer\account.ini', encoding='utf-8', errors='ignore').read()
PWD = re.search(r'\[ACCOUNT\]\s*\n\s*pass\s*=\s*(\S+)', ini).group(1)


def dmd5(p):
    return hashlib.md5(hashlib.md5(p.encode()).hexdigest().encode()).hexdigest().encode()


MD5_1 = hashlib.md5(PWD.encode()).hexdigest().encode()


def b103(p32):
    return (p32.ljust(32, b'\x00') + b'\x00' * 4 + b'\x00\x00\x00\x02' + b'\x00' * 4 +
            b'\x00' * 16 + b'\x00' * 6 + b'0'.ljust(64, b'\x00'))


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def drain(s, wait=2.5):
    s.settimeout(wait)
    out = b''
    try:
        while True:
            c = s.recv(8192)
            if not c:
                return out, 'closed'
            out += c
    except socket.timeout:
        return out, 'timeout'


def parse(tag, data):
    if not data:
        print('   %-10s (nothing)' % tag); return True
    p = 0
    while p + 17 <= len(data):
        ln = struct.unpack_from('>I', data, p)[0]
        if ln < 17 or p + ln > len(data):
            print('   %-10s raw %s' % (tag, data[p:p + 24].hex())); return True
        print('   %-10s <= cmd=%-5d len=%-4d res=%-4d body=%s' % (
            tag, struct.unpack_from('>I', data, p + 5)[0], ln,
            struct.unpack_from('>i', data, p + 13)[0], data[p + 17:p + min(ln, 33)].hex()))
        p += ln
    return True


def run(tag, steps, wait=2.5):
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
            print('   %-10s send fail %s' % (name, e)); return
        data, why = drain(s, wait)
        if why == 'closed':
            print('   %-10s -> closed' % name); s.close(); return
        parse(name, data)
    s.close()


gate = [('105', frame(105, SESS + b'\x00' * 4)), ('111', frame(111)),
        ('109', frame(109, SESS + b'\x00' * 4))]

run('[A] 105 -> 103(dmd5)', gate[:1] + [('103', frame(103, b103(dmd5(PWD))))])
run('[B] 105 ->111->109 -> 103(dmd5)', gate + [('103', frame(103, b103(dmd5(PWD))))])
run('[C] 105 ->111->109 -> 103(md5)', gate + [('103', frame(103, b103(MD5_1)))])
run('[D] 109 -> 103(dmd5)', [('109', frame(109, SESS + b'\x00' * 4)), ('103', frame(103, b103(dmd5(PWD))))])