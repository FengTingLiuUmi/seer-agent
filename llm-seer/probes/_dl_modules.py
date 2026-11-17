import urllib.request as u, zlib, re
for name in ('RobotCoreDLL.swf','RobotAppDLL.swf'):
    url='http://seer.61.com/dll/'+name
    try:
        d=u.urlopen(url,timeout=20).read()
    except Exception as e:
        print(name,'ERR',type(e).__name__,str(e)[:60]); continue
    open(name,'wb').write(d)
    print(name,len(d),d[:8].hex(' '),'magic',d[:3])
    try:
        v=zlib.decompress(d[7:]); v2=zlib.decompress(v[8:])
        open(name.replace('.swf','.dec.swf'),'wb').write(b'FWS'+v[3:8]+v2)
        print('   decrypted',len(v2))
    except Exception as e:
        print('   decrypt fail',type(e).__name__,str(e)[:40])
