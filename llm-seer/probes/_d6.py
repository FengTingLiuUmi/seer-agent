import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

blk = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')[0]
L = len(blk)


def traits(r):
    n = r.u30()
    for _ in range(n):
        r.u30(); k = r.u8(); base = k & 0x0f
        if base in (0, 6):
            r.u30(); r.u30(); vi = r.u30()
            if vi: r.u8()
        elif base in (1, 2, 3, 4, 5): r.u30(); r.u30()
        else: raise ValueError('k')
        if k & 0x40:
            c = r.u30()
            for _ in range(c): r.u30()


def bodies(r, cnt):
    out = []
    for _ in range(cnt):
        mi = r.u30(); ms = r.u30(); ml = r.u30(); isd = r.u30(); msd = r.u30()
        cl = r.u30(); code = r.raw(cl)
        ec = r.u30()
        for _ in range(ec):
            for _ in range(5): r.u30()
        traits(r)
        out.append((mi, ms, ml, isd, msd, cl, code[:6].hex(' ')))
    return out


for s in range(380, 460):
    for cnt in (1, 2, 3, 4):
        r = R(blk, s)
        try:
            out = bodies(r, cnt)
        except Exception:
            continue
        if r.p == L:
            print('START', s, 'count', cnt, out)