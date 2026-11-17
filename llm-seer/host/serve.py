"""给 Flash 客户端用的静态服务器：把每个请求追加写到 site-requests.log，便于外部观察"""
import http.server, socketserver, os, sys, time, mimetypes

ROOT = sys.argv[1] if len(sys.argv) > 1 else 'site'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
LOG = os.path.join(os.path.dirname(os.path.abspath(ROOT)), 'site-requests.log')

mimetypes.add_type('application/x-shockwave-flash', '.swf')
mimetypes.add_type('text/xml', '.xml')


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        line = '%s %s\n' % (time.strftime('%H:%M:%S'), fmt % args)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line)
            f.flush()


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('127.0.0.1', PORT), H) as httpd:
    open(LOG, 'a').write('--- start %s port %d root %s ---\n' % (time.strftime('%H:%M:%S'), PORT, ROOT))
    httpd.serve_forever()