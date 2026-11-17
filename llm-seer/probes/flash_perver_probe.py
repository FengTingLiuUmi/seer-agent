import socket, struct, json

INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def probe(host, port, sends, wait=4, policy=True):
    tag = '%s:%d' % (host, port)
    try:
        s = socket.create_connection((host, port), timeout=5)
    except Exception as e:
        print('%-24s connect fail: %s' % (tag, e)); return
    pol = b''
    if policy:
        try:
            s.sendall(b'<policy-file-request/>\x00')
            s.settimeout(3)
            pol = s.recv(2048)
        except Exception as e:
            pol = b''
        s.close()
        try:
            s = socket.create_connection((host, port), timeout=5)
        except Exception as e:
            print('%-24s reconnect fail %s' % (tag, e)); return
    print('%-24s policy=%d %s' % (tag, len(pol), pol[:30]))
    for f in sends:
        try:
            s.sendall(f)
        except Exception as e:
            print('   send fail', e); return
    s.settimeout(wait)
    out = b''
    why = 'timeout'
    try:
        while len(out) < 65536:
            c = s.recv(8192)
            if not c:
                why = 'closed'; break
            out += c
    except socket.timeout:
        pass
    s.close()
    print('   %-8s recv=%d' % (why, len(out)))
    p = 0
    while p + 17 <= len(out):
        ln = struct.unpack_from('>I', out, p)[0]
        if ln < 17 or p + ln > len(out):
            print('   raw', out[p:p + 32].hex()); break
        print('   <= cmd=%-5d len=%-5d res=%-5d body=%s' % (
            struct.unpack_from('>I', out, p + 5)[0], ln,
            struct.unpack_from('>i', out, p + 13)[0], out[p + 17:p + min(ln, 49)].hex()))
        p += ln


targets = [('101.43.19.60', 1219), ('101.35.207.167', 1272), ('101.35.207.167', 1273)]
for h, p in targets:
    probe(h, p, [frame(101)])
for h, p in targets:
    probe(h, p, [frame(1001, bytes(508))])