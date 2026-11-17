import sys, itertools
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

MN_KINDS = (0x07, 0x0d, 0x0f, 0x10, 0x11, 0x12, 0x09, 0x0e, 0x1b, 0x1c, 0x1d)


def full(raw, s, dMet, dMeth, dInst, dCls, dScr, dBod, dTr):
    r = R(raw, s)
    # int/uint/double pools: assume they precede s; read counts here is wrong, so we
    # start directly at string pool (caller passes s).
    n = r.u30(); strs = [None]
    for _ in range(max(0, n - 1)): strs.append(r.raw(r.u30()).decode('utf-8', 'replace'))
    n = r.u30(); nss = [None]
    for _ in range(max(0, n - 1)):
        k = r.u8(); nss.append((k, r.u30()))
    n = r.u30()
    for _ in range(max(0, n - 1)):
        c = r.u30()
        for _ in range(c): r.u30()
    n = r.u30(); mns = [None]
    for _ in range(max(0, n - 1)):
        k = r.u8(); e = [k]
        if k in (0x07, 0x0d): e += [r.u30(), r.u30()]
        elif k in (0x0f, 0x10): e += [r.u30()]
        elif k in (0x11, 0x12): pass
        elif k in (0x09, 0x0e): e += [r.u30(), r.u30()]
        elif k in (0x1b, 0x1c): e += [r.u30()]
        elif k == 0x1d:
            e += [r.u30()]; c = r.u30(); e += [r.u30() for _ in range(c)]
        else: raise ValueError('mnk')
        mns.append(e)
    n = r.u30()
    for _ in range(max(0, n - dMeth)):
        pc = r.u30(); rt = r.u30()
        for _ in range(pc): r.u30()
        r.u30(); fl = r.u8()
        if fl & 0x08:
            oc = r.u30()
            for _ in range(oc): r.u30(); r.u8()
    n = r.u30()
    for _ in range(max(0, n - dMet)):
        r.u30(); c = r.u30()
        for _ in range(c): r.u30(); r.u30()

    def traits():
        n = r.u30()
        for _ in range(max(0, n - dTr)):
            r.u30(); k = r.u8(); b = k & 0x0f
            if b in (0, 6):
                r.u30(); r.u30(); vi = r.u30()
                if vi: r.u8()
            elif b in (1, 2, 3, 4, 5): r.u30(); r.u30()
            else: raise ValueError('tk %x' % b)
            if k & 0x40:
                c = r.u30()
                for _ in range(c): r.u30()

    n = r.u30()
    for _ in range(max(0, n - dInst)):
        r.u30(); r.u30(); fl = r.u8()
        if fl & 0x08: r.u30()
        c = r.u30()
        for _ in range(c): r.u30()
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dCls)):
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dScr)):
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dBod)):
        r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
        cl = r.u30(); r.raw(cl)
        ec = r.u30()
        for _ in range(ec):
            for _ in range(5): r.u30()
        traits()
    return r.p


for f, s in (('Client.swf', 49), ('Login.swf', 1216)):
    raw = avm2.read_swf(f)[0]
    hits = []
    for conv in itertools.product([0, 1], repeat=7):
        try:
            p = full(raw, s, *conv)
        except Exception:
            continue
        if abs(p - len(raw)) < 8:
            hits.append((len(raw) - p, conv))
    print(f, 'len', len(raw), 'hits', hits[:6])