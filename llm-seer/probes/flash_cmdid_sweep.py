import socket, struct, json, sys
from concurrent.futures import ThreadPoolExecutor

INFO = json.load(open('login.json', encoding='utf-8'))
UID = INFO['uid']
CMDS = json.load(open('../seer-auto/commandid.json', encoding='utf-8'))
BY_ID = {}
for k, v in CMDS.items():
    BY_ID.setdefault(v, k)

HOST = (sys.argv[1], int(sys.argv[2])) if len(sys.argv) > 2 else ('101.35.207.167', 1272)
WAIT = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5


def frame(cmd, body=b'', r=0):
    return (struct.pack('>I', 17 + len(body)) + b'\x31' + struct.pack('>I', cmd) +
            struct.pack('>I', UID) + struct.pack('>i', r) + body)


def probe(cmd):
    try:
        s = socket.create_connection(HOST, timeout=4)
    except Exception:
        return cmd, 'connfail', b''
    try:
        s.sendall(frame(cmd))
        s.settimeout(WAIT)
        out = b''
        why = 'timeout'
        try:
            while len(out) < 8192:
                c = s.recv(4096)
                if not c:
                    why = 'closed'
                    break
                out += c
                break
        except socket.timeout:
            pass
        return cmd, why, out
    finally:
        s.close()


hits = []
ids = sorted(BY_ID)
with ThreadPoolExecutor(max_workers=32) as ex:
    for cmd, why, out in ex.map(probe, ids):
        if why != 'closed':
            hits.append((cmd, BY_ID[cmd], why, out[:33].hex()))
print('%s:%d  tested=%d  non-closed=%d' % (HOST[0], HOST[1], len(ids), len(hits)))
for h in sorted(hits):
    print('  cmd=%-6d %-22s %-8s %s' % h)