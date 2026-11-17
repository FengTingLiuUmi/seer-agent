"""通过代理发一条 101（GET_VERIFCODE），验证代理链路 + 帧解析"""
import socket, struct, sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18630
UID = ACCOUNT


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


s = socket.create_connection(('127.0.0.1', PORT), timeout=6)
s.sendall(b'<policy-file-request/>\x00')
pol = s.recv(2048)
print('policy via proxy:', pol[:50], '...', len(pol), 'bytes')
s.close()

s = socket.create_connection(('127.0.0.1', PORT), timeout=6)
s.sendall(frame(101))
s.settimeout(5)
out = b''
try:
    while len(out) < 4096:
        c = s.recv(4096)
        if not c:
            break
        out += c
except socket.timeout:
    pass
s.close()
if len(out) >= 17:
    print('S2C cmd=%d len=%d res=%d body=%s' % (
        struct.unpack_from('>I', out, 5)[0], struct.unpack_from('>I', out, 0)[0],
        struct.unpack_from('>i', out, 13)[0], out[17:].hex()))
else:
    print('no reply, recv=%d' % len(out))