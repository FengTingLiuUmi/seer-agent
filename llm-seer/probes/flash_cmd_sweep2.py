import socket, struct, sys
HOST=('101.43.19.60',1863); UID=ACCOUNT
def frame(cmd, body=b'', r=0):
    return (struct.pack('>I',17+len(body))+b'\x31'+struct.pack('>I',cmd)+
            struct.pack('>I',UID)+struct.pack('>i',r)+body)
def probe(cmd, wait=1.5):
    s=socket.create_connection(HOST,timeout=5)
    try:
        s.sendall(b'<policy-file-request/>\x00'); s.recv(1024)
    except Exception: pass
    s.close(); s=socket.create_connection(HOST,timeout=5)
    s.sendall(frame(cmd)); s.settimeout(wait)
    out=b''; why='timeout'
    try:
        while True:
            c=s.recv(4096)
            if not c: why='closed'; break
            out+=c
    except socket.timeout: pass
    s.close(); return why,out
cmds=list(range(100,141))+list(range(1000,1011))+[900,901,101,102,106,108,110,112]
ok=[]
for c in cmds:
    try: why,out=probe(c)
    except Exception as e: continue
    if why!='closed': ok.append((c,why,len(out),out[:17].hex()))
print('tested',len(cmds),'non-closed',len(ok))
for x in ok: print('  cmd=%-5d %-8s %s' % (x[0],x[1],x[3]))
