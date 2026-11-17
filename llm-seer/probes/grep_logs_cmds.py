import json,base64,struct,glob,os
want={2303,2301,2311,2313,2707,2875,2876,2877,2114,2201}
found={}
for f in glob.glob('seer-auto/*.jsonl')+glob.glob('seer-auto/tools/*.jsonl'):
    for ln in open(f,encoding='utf-8',errors='ignore'):
        try:o=json.loads(ln)
        except:continue
        if o.get('kind')!='C2S' or not o.get('b64'):continue
        try:raw=base64.b64decode(o['b64'])
        except:continue
        if len(raw)<17:continue
        c=struct.unpack_from('>I',raw,5)[0]
        if c in want:
            found.setdefault(c,[]).append((os.path.basename(f),raw[17:].hex()))
print('cmds with bodies:', {k:len(v) for k,v in found.items()})
for c,v in sorted(found.items()):
    print(c, v[:2])
