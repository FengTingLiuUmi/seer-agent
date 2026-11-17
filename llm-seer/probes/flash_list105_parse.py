import socket, struct, json, re

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def get105():
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
        while True:
            c = s.recv(8192)
            if not c:
                break
            out += c
    except socket.timeout:
        pass
    s.close()
    return out


raw = get105()
body = raw[17:]
open('list105.bin', 'wb').write(body)
print('total', len(raw), 'body', len(body))

ips = [(m.start(), m.group().decode()) for m in re.finditer(rb'\d{1,3}(?:\.\d{1,3}){3}', body)]
print('ips', len(ips))
if len(ips) > 2:
    deltas = [ips[i + 1][0] - ips[i][0] for i in range(min(6, len(ips) - 1))]
    print('deltas', deltas)
for off, ip in ips[:8]:
    print('ip@%-4d %-16s ctx=%s' % (off, ip, body[max(0, off - 12):off + 24].hex(' ')))
print('head 64:', body[:64].hex(' '))
print('tail 48:', body[-48:].hex(' '))