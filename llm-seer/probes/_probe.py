import collections,sys,re
for name in ("TaomeeLibraryDLL.swf","Login.swf"):
    try: d=open(name,'rb').read()
    except Exception as e: print(name,e); continue
    print("==",name,len(d),d[:8].hex(' '))
    c=collections.Counter(d)
    print("top bytes:",[(hex(b),n) for b,n in c.most_common(6)])
    z=d.count(b'78 9c'.replace(b' ',b''))
    print("zlib78da@:",[m.start() for m in re.finditer(b'\x78[\x01\x5e\x9c\xda]',d)][:6])
    for pat in (b'SocketImpl',b'HeadInfo',b'pack',b'doABC',b'Socket',b'Taomee'):
        i=d.find(pat); print(pat.decode(),i)
