import socket, struct, json
INFO=json.load(open('login.json',encoding='utf-8')); SESS=bytes.fromhex(INFO['sessionHex']); UID=INFO['uid']
def frame(cmd, body=b''):
    r=0
    if cmd>1000:
        x=0
        for b in body: x^=b
        r = 113 + len(body)%17 + cmd%23 + x + 7
    return (struct.pack('>I',17+len(body))+b'\x31'+struct.pack('>I',cmd)+
            struct.pack('>I',UID)+struct.pack('>i',r)+body)
def t(tag,host,port,payload,wait=3):
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
    s.close(); print('%-34s %-8s recv=%d %s' % (tag,why,len(out),out[:40].hex()))
g=('101.35.207.167',1272)
t('sess16 + 1001 frame', *g, SESS+frame(1001,b''))
t('1001 frame + sess16', *g, frame(1001,b'')+SESS)
t('sess16 + 1001 zeros508', *g, SESS+frame(1001,b'\x00'*508))
t('1001 with 16B prefix inside body', *g, frame(1001,SESS+b'\x00'*16))
