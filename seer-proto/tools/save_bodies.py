import re, os, glob

os.makedirs('bodies', exist_ok=True)
got = {}
for path in glob.glob('*.log'):
    t = open(path, 'rb').read().decode('utf-16-le', errors='replace')
    for ln in t.splitlines():
        m = re.search(r'S2C cmd=(\d+) len=\d+ res=(-?\d+) body=([0-9a-f]*)', ln)
        if not m:
            continue
        cmd, res, hexb = int(m.group(1)), int(m.group(2)), m.group(3)
        if cmd > 70000 or res != 0:
            continue
        if cmd in (8002, 3452, 45963, 2002):
            continue
        if not hexb:
            continue
        got.setdefault(cmd, bytes.fromhex(hexb))

for cmd, b in sorted(got.items()):
    open('bodies/%d.bin' % cmd, 'wb').write(b)
print('saved', len(got), 'bodies:', sorted(got))
print('sizes', {c: len(b) for c, b in sorted(got.items())})