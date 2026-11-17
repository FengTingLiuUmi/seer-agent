import os, re, urllib.request as u

OUT = 'llm-seer/patch/seer_pages'
os.makedirs(OUT, exist_ok=True)

for url, name in (('https://seer.61.com/', 'index.html'),
                  ('https://seer.61.com/play.shtml', 'play.html')):
    try:
        raw = u.urlopen(url, timeout=20).read()
        open(os.path.join(OUT, name), 'wb').write(raw)
        d = raw.decode('utf-8', 'replace')
        print('==', url, len(d), 'bytes ->', os.path.join(OUT, name))
        for pat, label in ((r'<iframe[^>]{0,240}', 'iframe'),
                           (r'<input[^>]{0,140}', 'input'),
                           (r'src="([^"]{3,140}\.js)"', 'js'),
                           (r'(login|account|passport|oauth)[A-Za-z0-9_./?=&%-]{2,80}', 'login-ref')):
            ms = re.findall(pat, d, re.I)[:6]
            print('  ', label, ms)
    except Exception as e:
        print(url, 'ERR', e)