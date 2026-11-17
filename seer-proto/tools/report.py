#!/usr/bin/env python3
"""把 session.jsonl 转成一页自包含 HTML 报告（双击即可看）。"""
import json, sys, html, collections, datetime, os

src = sys.argv[1] if len(sys.argv) > 1 else 'session.jsonl'
out = sys.argv[2] if len(sys.argv) > 2 else 'report.html'

evs = []
for line in open(src, encoding='utf-8', errors='replace'):
    line = line.strip()
    if not line:
        continue
    try:
        evs.append(json.loads(line))
    except Exception:
        pass


def dec(body_hex):
    if not body_hex:
        return ''
    try:
        b = bytes.fromhex(body_hex)
    except Exception:
        return ''
    s = b.decode('utf-8', 'replace')
    return ''.join(c if (c.isprintable() and c != '\ufffd') else '.' for c in s)


cnt = collections.Counter(e.get('dir') for e in evs)
cmds = collections.Counter('%d %s' % (e['cmd'], e.get('name', '')) for e in evs if e.get('dir') == 'c2s')

rows = []
for e in evs:
    d = e.get('dir', '')
    t = datetime.datetime.fromtimestamp(e.get('t', 0) / 1000).strftime('%H:%M:%S.%f')[:-3]
    body = e.get('body', '')
    rows.append(
        '<tr class="%s"><td>%s</td><td>%s</td><td>%s</td><td class="n">%s</td>'
        '<td>%s</td><td>%s</td><td class="b">%s</td></tr>' % (
            html.escape(d), t, html.escape(d.upper()), e.get('cmd', ''),
            html.escape(e.get('name', '')), e.get('len', ''), e.get('res', ''),
            html.escape(dec(body)[:100]) + ('<span class="hx"> ' + html.escape(body[:120]) + '</span>' if body else '')
            if not e.get('msg') else html.escape(e['msg'])))

page = """<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>seer 会话报告</title>
<style>
body{font:13px/1.5 ui-monospace,Consolas,monospace;background:#11151c;color:#d5dae3;margin:0;padding:16px}
h1{font-size:16px;color:#9fd3ff;margin:0 0 6px}
.sum{color:#8b98a8;margin-bottom:12px}
table{border-collapse:collapse;width:100%%}td{padding:2px 6px;border-bottom:1px solid #1c2531;vertical-align:top}
.c2s{color:#7ee787}.s2c{color:#79c0ff}.info{color:#c8a2ff}.err{color:#ff7b72}
.n{color:#5c6773}.b{color:#8b98a8;word-break:break-all}.hx{color:#3d4757}
</style></head><body>
<h1>赛尔号客户端 · 会话报告</h1>
<div class="sum">%d 条事件 · c2s %d / s2c %d / info %d / err %d · 命令: %s</div>
<table>%s</table></body></html>"""

summary = ' / '.join('%s×%d' % (k, v) for k, v in cmds.most_common(12))
open(out, 'w', encoding='utf-8').write(page % (
    len(evs), cnt.get('c2s', 0), cnt.get('s2c', 0), cnt.get('info', 0), cnt.get('err', 0),
    html.escape(summary), '\n'.join(rows)))
print('written', out, len(evs), 'events')