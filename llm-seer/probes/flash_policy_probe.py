import socket

HOSTS = [('101.43.19.60', 1863), ('101.43.19.60', 1864), ('111.229.85.11', 1863), ('111.229.85.11', 1864)]


def probe(host, port, payload, label, wait=3.0):
    try:
        s = socket.create_connection((host, port), timeout=5)
    except Exception as e:
        print(host, port, label, 'CONNECT ERR', e)
        return
    s.settimeout(wait)
    data = b''
    try:
        if payload:
            s.sendall(payload)
        while True:
            c = s.recv(1024)
            if not c:
                break
            data += c
    except socket.timeout:
        pass
    except Exception as e:
        print(host, port, label, 'IO ERR', e)
    print(host, port, label, 'recv', len(data), data[:80])
    s.close()


for h, p in HOSTS:
    probe(h, p, b'<policy-file-request/>\x00', 'policy')
    probe(h, p, b'', 'silent')