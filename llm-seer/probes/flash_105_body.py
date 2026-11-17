import socket, struct, json

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0, ver=b'\x31'):
    return (struct.pack('>I', 17 + len(body)) + ver + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


s = socket.create_connection(HOST, timeout=6)
s.sendall(b'<policy-file-request/>\x00')
try:
    s.recv(1024)
except Exception:
    pass
s.close()
s = socket.create_connection(HOST, timeout=6)
s.sendall(frame(105, SESS + b'\x00' * 4))
s.settimeout(4)
out = b''
try:
    while len(out) < 16384:
        c = s.recv(8192)
        if not c:
            break
        out += c
except socket.timeout:
    pass
s.close()
print('recv', len(out))
body = out[17:]
print('body len', len(body))
for i in range(0, min(len(body), 320), 16):
    chunk = body[i:i + 16]
    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print('%04x  %-47s  %s' % (i, chunk.hex(' '), asc))