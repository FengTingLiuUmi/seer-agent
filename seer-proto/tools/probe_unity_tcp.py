import json, socket, struct, sys, time

uid = ACCOUNT
sess = bytes.fromhex(json.load(open('seer-proto/login.json', encoding='utf-8'))['sessionHex'])


def frame(cmd, body=b'', res=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', uid) + struct.pack('>i', res) + body)


def parse(buf):
    out = []
    off = 0
    while off + 17 <= len(buf):
        ln = struct.unpack_from('>I', buf, off)[0]
        if ln < 17 or off + ln > len(buf):
            break
        cmd = struct.unpack_from('>I', buf, off + 5)[0]
        res = struct.unpack_from('>i', buf, off + 13)[0]
        body = buf[off + 17:off + ln]
        out.append((cmd, ln, res, body[:24].hex()))
        off += ln
    return out


for host, port in (('101.35.140.183', 1864), ('111.229.168.25', 1863)):
    print('== try', host, port)
    try:
        s = socket.create_connection((host, port), timeout=6)
    except Exception as e:
        print('   connect fail', e)
        continue
    s.settimeout(1.2)
    # 1) 策略文件
    try:
        s.sendall(b'<policy-file-request/>\x00')
        pol = s.recv(4096)
        print('   policy', len(pol), pol[:40])
    except Exception as e:
        print('   policy fail', e)
    s.close()
    try:
        s = socket.create_connection((host, port), timeout=6)
        s.settimeout(1.5)
        for body_name, body in (('sess+4z', sess + b'\x00' * 4), ('sess', sess)):
            s.sendall(frame(105, body))
            time.sleep(0.4)
            try:
                d = s.recv(65536)
            except Exception as e:
                print('   %s -> recv %s' % (body_name, e))
                continue
            print('   %s -> %d bytes' % (body_name, len(d)), parse(d)[:3])
        s.close()
    except Exception as e:
        print('   data conn fail', e)