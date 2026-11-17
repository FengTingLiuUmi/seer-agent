import json, socket, struct, time

uid = ACCOUNT
j = json.load(open('seer-proto/login.json', encoding='utf-8'))
sess = bytes.fromhex(j['sessionHex'])
body_b64 = j.get('bodyB64')
template = bytes.fromhex('') if not body_b64 else __import__('base64').b64decode(body_b64)


def frame(cmd, body=b'', res=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', uid) + struct.pack('>i', res) + body)


def parse(buf):
    out, off = [], 0
    while off + 17 <= len(buf):
        ln = struct.unpack_from('>I', buf, off)[0]
        if ln < 17 or off + ln > len(buf):
            break
        cmd = struct.unpack_from('>I', buf, off + 5)[0]
        res = struct.unpack_from('>i', buf, off + 13)[0]
        out.append((cmd, ln, res))
        off += ln
    return out


TARGETS = [('111.229.41.195', 1219), ('111.229.41.195', 1863), ('111.229.41.195', 1864)]

for host, port in TARGETS:
    print('== %s:%d' % (host, port))
    try:
        s = socket.create_connection((host, port), timeout=5)
    except Exception as e:
        print('   connect fail:', e)
        continue
    s.settimeout(2.0)
    try:
        s.sendall(b'<policy-file-request/>\x00')
        pol = s.recv(2048)
        print('   policy:', len(pol))
    except Exception as e:
        print('   policy err:', e)
    s.close()

    try:
        s = socket.create_connection((host, port), timeout=5)
        s.settimeout(2.5)
        # 试 1001（session 写入前 16 字节）
        b = bytearray(template) if template else bytearray(508)
        b[0:16] = sess
        s.sendall(frame(1001, bytes(b)))
        time.sleep(0.6)
        try:
            d = s.recv(65536)
            print('   1001 ->', len(d), 'bytes', parse(d)[:5])
        except Exception as e:
            print('   1001 recv:', e)
        s.close()
    except Exception as e:
        print('   conn2 fail:', e)