import socket, struct, json
INFO=json.load(open('login.json',encoding='utf-8')); SESS=bytes.fromhex(INFO['sessionHex']); UID=INFO['uid']
def frame(cmd, body=b'', uid=None, r=None):
    uid = UID if uid is None else uid
    if r is None:
        r=0
        if cmd>1000:
            x=0
            for b in body: x^=b
            r = 113 + len(body)%17 + cmd%23 + x + 7
    return (struct.pack('>I',17+len(body))+b'\x31'+struct.pack('>I',cmd)+
            struct.pack('>I',uid)+struct.pack('>i',r)+body)
def t(tag, host, port, payload, wait=2.5):
    s=socket.create_connection((host,port),timeout=4)
    s.sendall(b'<policy-file-request/>\x00')
    try:
        s.settimeout(2); s.recv(2048)
    except Exception: pass
    s.close(); s=socket.create_connection((host,port),timeout=4)
    s.sendall(payload); s.settimeout(wait)
    why='timeout'; out=b''
    try:
        while True:
            c=s.recv(4096)
            if not c: why='closed'; break
            out+=c
    except socket.timeout: pass
    s.close(); print('%-32s %-8s recv=%d %s' % (tag,why,len(out),out[:32].hex()))
g=('101.35.207.167',1272)
t('1001 body0 uid0', *g, frame(1001,b'',uid=0))
t('1001 body0 r0', *g, frame(1001,b'',r=0))
t('1001 body0 rcalc', *g, frame(1001,b''))
t('1001 sess16', *g, frame(1001,SESS))
t('1001 sess16 uid0', *g, frame(1001,SESS,uid=0))
t('1001 508 uid0', *g, frame(1001,b'\x00'*508,uid=0))
t('1002 uid0', *g, frame(1002,b'',uid=0))
t('1002 r0', *g, frame(1002,b'',r=0))
