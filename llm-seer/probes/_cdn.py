import urllib.request as u
for p in ('http://seer.61.com/ip','http://seer.61.com/seer.xml','http://seer.61.com/config/seer.xml','http://seer.61.com/main/seer.xml'):
    try:
        r=u.urlopen(p,timeout=8); d=r.read(300)
        print(p, r.status, len(d), d[:120])
    except Exception as e:
        print(p,'ERR',type(e).__name__,str(e)[:60])
