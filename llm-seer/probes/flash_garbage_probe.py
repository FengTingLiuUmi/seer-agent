import socket, struct, time
def t(host, port, payload, wait=2.5, tag=''):
    s=socket.create_connection((host,port),timeout=4)
    t0=time.time(); s.sendall(payload); s.settimeout(wait)
    why='timeout'; out=b''
    try:
        while True:
            c=s.recv(4096)
            if not c: why='closed'; break
            out+=c
    except socket.timeout: pass
    dt=(time.time()-t0)*1000; s.close()
    print('%-26s %-8s %6.0fms recv=%d %s' % (tag, why, dt, len(out), out[:20].hex()))
g=('101.35.207.167',1272); login=('101.43.19.60',1863)
t(*g, b'\x00'*17, tag='game 17 zero bytes')
t(*g, b'\x00', tag='game 1 byte')
t(*g, b'GET / HTTP/1.0\r\n\r\n', tag='game http probe')
t(*login, b'\x00'*17, tag='1863 17 zero bytes')
t(*login, b'\x00', tag='1863 1 byte')
