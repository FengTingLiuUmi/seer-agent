import socket, struct, json, itertools

HOST = ('101.43.19.60', 1863)
INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
SESS = bytes.fromhex(INFO['sessionHex'])


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def session_conn():
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    try:
        s.recv(1024)
    except Exception:
        pass
    s.close()
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(frame(109, SESS + struct.pack('>I', 0)))  # login first? try 105 instead
    return s


def one(cmd, body, wait=2.0):
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(b'<policy-file-request/>\x00')
    try:
        s.recv(1024)
    except Exception:
        pass
    s.close()
    s = socket.create_connection(HOST, timeout=6)
    s.sendall(frame(cmd, body))
    s.settimeout(wait)
    out = b''
    why = 'timeout'
    try:
        while True:
            c = s.recv(8192)
            if not c:
                why = 'closed'; break
            out += c
    except socket.timeout:
        pass
    s.close()
    return why, out


# 105 列表里出现的 serverId 候选
ids = [0, 1, 3002, 3500, 485, 486, 487, 488, 489, 493, 494, 505, 1269, 1273, 1277]
for sid in ids:
    why, out = one(109, SESS + struct.pack('>I', sid))
    if out:
        ln = struct.unpack_from('>I', out, 0)[0]
        print('109 sid=%-5d %-8s len=%-4d cmd=%-4d res=%-4d body=%s' % (
            sid, why, ln, struct.unpack_from('>I', out, 5)[0],
            struct.unpack_from('>i', out, 13)[0], out[17:17 + min(40, len(out) - 17)].hex()))
    else:
        print('109 sid=%-5d %-8s (no data)' % (sid, why))