import sys, itertools
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

b = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')
blk = b[0]


def parse(raw, f):
    dM, dI, dC, dS, dB, dT = f
    r = R(raw)
    r.u16(); r.u16()
    pools = {}
    for idx in range(5):
        n = r.u30(); pools[idx] = n
        if idx == 0:
            for _ in range(max(0, n - 1)): r.s32()
        elif idx == 1:
            for _ in range(max(0, n - 1)): r.u32()
        elif idx == 2:
            for _ in range(max(0, n - 1)): r.d64()
        elif idx == 3:
            for _ in range(max(0, n - 1)): r.raw(r.u30())
        else:
            for _ in range(max(0, n - 1)): r.u8(); r.u30()
    nsets = r.u30()
    for _ in range(max(0, nsets - 1)):
        c = r.u30()
        for _ in range(c): r.u30()
    nmn = r.u30()
    for _ in range(max(0, nmn - 1)):
        k = r.u8()
        if k in (0x07, 0x0d): r.u30(); r.u30()
        elif k in (0x0f, 0x10): r.u30()
        elif k in (0x11, 0x12): pass
        elif k in (0x09, 0x0e): r.u30(); r.u30()
        elif k in (0x1b, 0x1c): r.u30()
        elif k == 0x1d:
            r.u30(); c = r.u30()
            for _ in range(c): r.u30()
        else: raise ValueError('mnk')
    nmeth = r.u30()
    for _ in range(nmeth):
        pc = r.u30(); rt = r.u30()
        for _ in range(pc): r.u30()
        r.u30(); fl = r.u8()
        if fl & 0x08:
            oc = r.u30()
            for _ in range(oc): r.u30(); r.u8()
    nmet = r.u30()
    for _ in range(max(0, nmet - dM)):
        r.u30(); c = r.u30()
        for _ in range(c): r.u30(); r.u30()

    def traits():
        n = r.u30(); cnt = n
        for _ in range(max(0, n - dT)):
            nm = r.u30(); k = r.u8(); base = k & 0x0f
            if base in (0, 6):
                r.u30(); r.u30(); vi = r.u30()
                if vi: r.u8()
            elif base in (1, 2, 3): r.u30(); r.u30()
            elif base == 4: r.u30(); r.u30()
            elif base == 5: r.u30(); r.u30()
            else: raise ValueError('traitkind %x' % base)
            if k & 0x40:
                c = r.u30()
                for _ in range(c): r.u30()
        return cnt

    n = r.u30(); ni = max(0, n - dI)
    for _ in range(ni):
        r.u30(); r.u30(); fl = r.u8()
        if fl & 0x08: r.u30()
        c = r.u30()
        for _ in range(c): r.u30()
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dC)):
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dS)):
        r.u30(); traits()
    n = r.u30(); nb = max(0, n - dB)
    for _ in range(nb):
        mi = r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
        cl = r.u30(); r.raw(cl)
        ec = r.u30()
        for _ in range(ec):
            for _ in range(5): r.u30()
        traits()
    return r.p


for combo in itertools.product([0, 1], repeat=6):
    try:
        p = parse(blk, combo)
    except Exception as e:
        continue
    if p == len(blk):
        print('EXACT', combo)
print('done; len', len(blk))