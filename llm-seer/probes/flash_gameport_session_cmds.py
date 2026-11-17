import socket, struct, json
INFO=json.load(open('login.json',encoding='utf-8')); SESS=bytes.fromhex(INFO['sessionHex']); UID=INFO['uid']
def frame(cmd, body=b'', r=0):
    return (struct.pack('>I',17+len(body))+b'\x31'+struct.pack('>I',cmd)+
            struct.pack('>I',UID)+struct.pack('>i',r)+body)
def run(tag,host,port,steps,wait=2.5):
    try:
        s=socket.create_connection((host,port),timeout=4)
    except Exception as e:
        print(tag,'connect fail',e); return
    try:
        s.sendall(b'<policy-file-request/>\x00'); s.settimeout(2); s.recv(2048)
    except Exception: pass
    s.close(); s=socket.create_connection((host,port),timeout=4)
    print(tag)
    for name,f in steps:
        s.sendall(f); s.settimeout(wait); out=b''
        try:
            while True:
                c=s.recv(8192)
                if not c:
                    print('   %-8s -> closed' % name); s.close(); return
                out+=c; break
        except socket.timeout: pass
        if out:
            ln=struct.unpack_from('>I',out,0)[0]
            print('   %-8s <= cmd=%d len=%d res=%d body=%s' % (name,
                struct.unpack_from('>I',out,5)[0],ln,struct.unpack_from('>i',out,13)[0],out[17:17+min(32,len(out)-17)].hex()))
        else: print('   %-8s (silent)' % name)
    s.close()
g=('101.35.207.167',1272)
SB=SESS+b'\x00'*4
for cmd in (104,105,106,108,109,111):
    run('%d with session body' % cmd, *g, [(str(cmd), frame(cmd, SB))])
run('105(sess) -> 109(sess) -> 1001', *g, [('105',frame(105,SB)),('109',frame(109,SB)),('1001',frame(1001,b'\x00'*508))])
