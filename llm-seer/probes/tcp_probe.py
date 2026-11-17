import socket
import sys
import time

hosts = [
    ('111.229.168.25', 1863),
    ('101.35.140.183', 1863),
    ('111.229.41.195', 1864),
]

for host, port in hosts:
    try:
        s = socket.create_connection((host, port), timeout=5)
        s.settimeout(2.5)
        data = b''
        try:
            while True:
                chunk = s.recv(256)
                if not chunk:
                    break
                data += chunk
                if len(data) > 512:
                    break
        except socket.timeout:
            pass
        print(host, port, 'recv', len(data), 'bytes:', data[:64].hex() or '(none)')
        s.close()
    except Exception as e:
        print(host, port, 'ERR', e)