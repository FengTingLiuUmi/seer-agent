import json, base64, struct
path=r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\relogin4.jsonl'
F=[]
for line in open(path,encoding='utf-8'):
    try:o=json.loads(line)
    except:continue
    if o.get('kind') not in ('C2S','S2C'):continue
    raw=base64.b64decode(o['b64'])
    F.append((o['kind'],o['t'],struct.unpack_from('>I',raw,5)[0],raw))
for i,(k,t,cmd,raw) in enumerate(F):
    if k=='S2C' and cmd==2001:
        body=raw[17:]
        print('2001 t=%d len=%d ver=%02x body0=%s' % (t,len(raw),raw[4],body[:24].hex()))
        for k2,t2,c2,r2 in F[i+1:i+3]:
            print('   next %s cmd=%d res=%d body=%s' % (k2,c2,struct.unpack_from('>i',r2,13)[0],r2[17:].hex()[:48]))
