import socket
import struct

HOST, PORT = '101.43.19.60', 1863
UID = ACCOUNT
ACCOUNT = b'ACCOUNT'
PASS = b'e10adc3949ba59abbe56e057f20f883e'


def pad(b, n):
    return b[:n] + b'\x00' * (max(0, n - len(b)))


state = [0]


def frame(cmd, body=b''):
    total = 17 + len(body)
    if cmd > 1000:
        s = 0
        for b in body:
            s ^= b
        v = state[0] - state[0] // 3 + 113 + len(body) % 17 + cmd % 23 + s + 7
        state[0] = v
        return struct.pack('>I', total) + b'\x31' + struct.pack('>I', cmd) + struct.pack('>I', UID) + struct.pack('>i', v) + body
    return struct.pack('>I', total) + b'\x31' + struct.pack('>I', cmd) + struct.pack('>I', UID) + struct.pack('>i', 0) + body


def login103():
    # 按 LoginManager.as: send(103, password32, tmcid, GAME_TYPE=2, 0, IGM_ID16, IMG_BY6, topTmcid)
    b = pad(PASS, 32)
    b += struct.pack('>I', 0)
    b += struct.pack('>I', 2)
    b += struct.pack('>I', 0)
    b += b'\x00' * 16
    b += b'\x00' * 6
    b += struct.pack('>I', 0)
    return b


s = socket.create_connection((HOST, PORT), timeout=5)
s.settimeout(3)
s.sendall(b'<policy-file-request/>\x00')
policy = s.recv(1024)
print('policy:', policy[:60], '...')

s.close()
s = socket.create_connection((HOST, PORT), timeout=5)
s.settimeout(6)
s.sendall(frame(103, login103()))
print('sent 103', 17 + len(login103()))
data = b''
try:
    while True:
        c = s.recv(4096)
        if not c:
            print('closed by server')
            break
        data += c
        if len(data) > 4096:
            break
except socket.timeout:
    print('recv timeout')
print('recv', len(data), data[:64].hex())
if len(data) >= 17:
    print('S2C cmd', struct.unpack_from('>I', data, 5)[0], 'len', struct.unpack_from('>I', data, 0)[0],
          'result', struct.unpack_from('>i', data, 13)[0], 'body', data[17:49].hex())
s.close()

