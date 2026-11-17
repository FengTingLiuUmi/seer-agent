import socket
import struct
import sys
import time

HOST, PORT = '101.43.19.60', 1863
UID = ACCOUNT
SESSION = bytes.fromhex('00000000000000000000000000000000')
ACCOUNT = b'ACCOUNT'
PASS_MD5 = b'e10adc3949ba59abbe56e057f20f883e'

state = [0]


def frame(cmd, body=b''):
    total = 17 + len(body)
    head = struct.pack('>IBIIi', total, 0x31, cmd, UID, 0)
    if cmd > 1000:
        s = 0
        for b in body:
            s ^= b
        v = state[0] - state[0] // 3 + 113 + len(body) % 17 + cmd % 23 + s + 7
        state[0] = v
        head = struct.pack('>IBII', total, 0x31, cmd, UID) + struct.pack('>i', v)
    return head + body


def pad(b, n):
    return b[:n] + b'\x00' * (n - len(b))


def login103():
    body = b''
    body += pad(ACCOUNT, 16)
    body += pad(PASS_MD5, 32)
    body += struct.pack('>I', 0)   # tmcid
    body += struct.pack('>I', 2)   # game type
    body += struct.pack('>I', 0)
    body += b'\x00' * 16           # IGM_ID
    body += b'\x00' * 6            # IMG_BY
    body += struct.pack('>I', 0)   # tmcid2
    body += struct.pack('>I', 0)   # channel id
    body += pad(b'flash_taomee', 32)
    return body


def try_cmd(name, cmd, body=b'', host=HOST, port=PORT):
    s = socket.create_connection((host, port), timeout=5)
    s.settimeout(6)
    s.sendall(frame(cmd, body))
    data = b''
    try:
        while True:
            c = s.recv(4096)
            if not c:
                break
            data += c
            if len(data) > 4096:
                break
    except socket.timeout:
        pass
    s.close()
    print(f'{name} cmd={cmd} sent={17+len(body)}B recv={len(data)}B {data[:48].hex()}')
    if len(data) >= 17:
        total = struct.unpack_from('>I', data, 0)[0]
        rcmd = struct.unpack_from('>I', data, 5)[0]
        res = struct.unpack_from('>i', data, 13)[0]
        print(f'   S2C cmd={rcmd} len={total} result={res} body={data[17:17+32].hex()}')


if __name__ == '__main__':
    try_cmd('103', 103, login103())
    time.sleep(0.5)
    try_cmd('105', 105, SESSION + b'\x00\x00\x00\x00')
    time.sleep(0.5)
    try_cmd('1001', 1001, pad(b'\x00' * 16, 16))
