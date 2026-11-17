"""解压 Login.swf（CWS→FWS）并列出与服务器相关的字符串"""
import zlib, re, sys, os

src = sys.argv[1] if len(sys.argv) > 1 else r'llm-seer\swf\Login.swf'
dst = sys.argv[2] if len(sys.argv) > 2 else r'llm-seer\dec\Login.fws.swf'
d = open(src, 'rb').read()
magic = d[:3]
if magic == b'CWS':
    body = zlib.decompress(d[8:])
    out = b'FWS' + d[3:8] + body
elif magic == b'FWS':
    out = d
else:
    raise SystemExit('bad magic %r' % magic)
open(dst, 'wb').write(out)
print('wrote', dst, len(out), 'bytes')

pats = [b'ip.txt', b'seerlogin', b'1863', b'1864', b'61.com', b'wss://', b'http://', b'https://', b'Server.xml',
        b'getServerList', b'RANGE_ONLINE', b'COMMEND_ONLINE', b'checkServer', b'getRecommendSvrList']
print('---- counts ----')
for p in pats:
    print('%-18s %d' % (p.decode(), out.count(p)))

# 抽出所有 URL / 域名 / ip:port 形态
txt = out
urls = sorted(set(re.findall(rb'https?://[A-Za-z0-9\.\-]+(?:/[A-Za-z0-9_\-/%\.\?=&]*)?', txt)))
hosts = sorted(set(re.findall(rb'[a-z0-9\-]+\.61\.com', txt)))
ips = sorted(set(re.findall(rb'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', txt)))
print('---- urls (%d) ----' % len(urls))
for u in urls[:20]:
    print('  ', u.decode('latin1'))
print('---- hosts (%d) ----' % len(hosts))
for h in hosts[:20]:
    print('  ', h.decode())
print('---- ips (%d) ----' % len(ips))
for i in ips[:10]:
    print('  ', i.decode())