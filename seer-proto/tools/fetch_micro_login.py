import os, re, urllib.request as u

OUT = 'llm-seer/patch/micro_login'
os.makedirs(OUT, exist_ok=True)

URLS = ['https://webres.61.com/common/flash/common_micro.html?game=seer_starter']
for url in URLS:
    try:
        raw = u.urlopen(url, timeout=20).read()
        name = 'common_micro.html'
        open(os.path.join(OUT, name), 'wb').write(raw)
        d = raw.decode('utf-8', 'replace')
        print('==', url, len(d), 'bytes')
        print(' iframe:', re.findall(r'<iframe[^>]{0,200}', d)[:3])
        print(' inputs:', re.findall(r'<input[^>]{0,120}', d)[:6])
        print(' js:', re.findall(r'src="([^"]{3,160}\.js)"', d)[:8])
        print(' sid refs:', re.findall(r'.{40}sid.{60}', d, re.I)[:4])
        print(' login refs:', re.findall(r'(https?://[A-Za-z0-9./?=&_%-]{6,90}(?:login|passport|account)[A-Za-z0-9./?=&_%-]{0,60})', d, re.I)[:5])
    except Exception as e:
        print(url, 'ERR', e)