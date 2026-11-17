import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

MN_KINDS = (0x07, 0x0d, 0x0f, 0x10, 0x11, 0x12, 0x09, 0x0e, 0x1b, 0x1c, 0x1d)


def parse_from(raw, s):
    """Parse ABC starting at the string-pool count (numeric pools skipped)."""
    r = R(raw, s)
    n = r.u30(); strs = [None]
    for _ in range(max(0, n - 1)): strs.append(r.raw(r.u30()).decode('utf-8', 'replace'))
    n = r.u30(); nss = [None]
    for _ in range(max(0, n - 1)):
        k = r.u8()
        if k > 0x1a: raise ValueError('nskind')
        nss.append((k, r.u30()))
    n = r.u30(); nssets = [None]
    for _ in range(max(0, n - 1)):
        c = r.u30(); nssets.append([r.u30() for _ in range(c)])
    n = r.u30(); mns = [None]
    for _ in range(max(0, n - 1)):
        k = r.u8()
        if k not in MN_KINDS: raise ValueError('mnkind %x' % k)
        e = [k]
        if k in (0x07, 0x0d): e += [r.u30(), r.u30()]
        elif k in (0x0f, 0x10): e += [r.u30()]
        elif k in (0x11, 0x12): pass
        elif k in (0x09, 0x0e): e += [r.u30(), r.u30()]
        elif k in (0x1b, 0x1c): e += [r.u30()]
        else:
            e += [r.u30()]; c = r.u30(); e += [r.u30() for _ in range(c)]
        mns.append(e)
    n = r.u30(); methods = [None]
    for _ in range(max(0, n - 1)):
        pc = r.u30(); rt = r.u30(); pt = [r.u30() for _ in range(pc)]
        nm = r.u30(); fl = r.u8()
        if fl & 0x08:
            oc = r.u30()
            for _ in range(oc): r.u30(); r.u8()
        methods.append((nm, pt, rt))
    n = r.u30()
    for _ in range(n):
        r.u30(); c = r.u30()
        for _ in range(c): r.u30(); r.u30()
    return r.p, len(strs), len(mns), len(methods)


for f in ('Client.swf', 'Login.swf'):
    raw = avm2.read_swf(f)[0]
    hits = []
    for s in range(4, 3000):
        try:
            p, ns, nm, nmeth = parse_from(raw, s)
        except Exception:
            continue
        if abs(p - len(raw)) < 200:
            hits.append((s, len(raw) - p, ns, nm, nmeth))
    print(f, len(raw), hits[:6])