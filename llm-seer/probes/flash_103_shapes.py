import socket, struct, json, hashlib, re

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])
PWD = re.search(r'\[ACCOUNT\]\s*\n\s*pass\s*=\s*(\S+)',
                open(r'F:\seer\account.ini', encoding='utf-8', errors='ignore').read()).group(1)
DMD5 = hashlib.md5(hashlib.md5(PWD.encode()).hexdigest().encode()).hexdigest().encode()
TOP = b'0'.ljust(64, b'\x00')


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def core(p32, tm=0, gt=2, z=0, igm=b'\x00' * 16, img=b'\x00' * 6):
    return p32.ljust(32, b'\x00') + struct.pack('>I', tm) + struct.pack('>I', gt) + \
        struct.pack('>I', z) + igm + img + TOP


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
        s.sendall(f)
        s.settimeout(wait)
        out = b''
        try:
            while True:
                c = s.recv(8192)
                if not c:
                    print('   %-8s -> closed' % name); s.close(); return
                out += c
                break
        except socket.timeout:
            pass
        if out:
            ln = struct.unpack_from('>I', out, 0)[0]
            print('   %-8s <= cmd=%d len=%d res=%d body=%s' % (
                name, struct.unpack_from('>I', out, 5)[0], ln,
                struct.unpack_from('>i', out, 13)[0], out[17:17 + min(32, len(out) - 17)].hex()))
        else:
            print('   %-8s (silent)' % name)
    s.close()


run('[a] 103 pass=dmd5 130B', [('103', frame(103, core(DMD5)))])
run('[b] 103 pass=session32', [('103', frame(103, core(SESS)))])
run('[c] 103 customID 194B', [('103', frame(103, SESS.ljust(64, b'\x00') + core(DMD5)))])
run('[d] 105(sess) -> 103 dmd5', [
    ('105', frame(105, SESS + b'\x00' * 4)),
    ('103', frame(103, core(DMD5)))])
run('[e] 105(sess) ->103 sess32', [
    ('105', frame(105, SESS + b'\x00' * 4)),
    ('103', frame(103, core(SESS)))])