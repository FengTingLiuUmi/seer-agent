"""下载并解密 Taomee 模块 SWF（7 字节前缀 + zlib(CWS) + 内层 zlib → FWS）"""
import os, sys, urllib.request as u, zlib

OUT = 'llm-seer/swf'
DEC = 'llm-seer/dec'
os.makedirs(OUT, exist_ok=True)
os.makedirs(DEC, exist_ok=True)


def decrypt(raw, dst):
    d = raw
    if d[:3] in (b'FWS', b'CWS', b'ZWS'):
        out = d
    else:
        prefix = d[:7]
        body = zlib.decompress(d[7:])
        # 内层常常还是 CWS
        if body[:3] == b'CWS':
            body = b'FWS' + body[3:8] + zlib.decompress(body[8:])
        elif body[:3] != b'FWS':
            body = b'FWS' + body[3:8] + body[8:]
        out = body
    open(dst, 'wb').write(out)
    return len(out)


for name in sys.argv[1:] or ['RobotApp_2DLL.swf']:
    url = 'https://seer.61.com/dll/' + name
    try:
        raw = u.urlopen(url, timeout=30).read()
    except Exception as e:
        print('download fail', name, e)
        continue
    src = os.path.join(OUT, name)
    open(src, 'wb').write(raw)
    dst = os.path.join(DEC, name.replace('.swf', '.dec.swf'))
    try:
        n = decrypt(raw, dst)
        print('OK', name, 'raw', len(raw), '-> dec', n)
    except Exception as e:
        print('decrypt fail', name, e)