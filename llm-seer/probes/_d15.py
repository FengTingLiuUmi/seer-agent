import sys, itertools
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')[0]
END = 418  # bodies count byte


def tryp(s, dMet, dIns, dCls, dScr, dTr):
    r = R(raw, s)
    n = r.u30()
    for _ in range(max(0, n - dMet)):
        r.u30(); c = r.u30()
        for _ in range(c): r.u30(); r.u30()

    def traits():
        n = r.u30()
        for _ in range(max(0, n - dTr)):
            nm = r.u30(); k = r.u8(); b = k & 0x0f
            if b in (0, 6):
                r.u30(); r.u30(); vi = r.u30()
                if vi: r.u8()
            elif b in (1, 2, 3, 4, 5): r.u30(); r.u30()
            else: raise ValueError('tk')
            if k & 0x40:
                c = r.u30()
                for _ in range(c): r.u30()

    n = r.u30()
    for _ in range(max(0, n - dIns)):
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
    return r.p


hits = []
for s in range(380, 406):
    for conv in itertools.product([0, 1], repeat=5):
        try:
            if tryp(s, *conv) == END:
                hits.append((s, conv))
        except Exception:
            pass
print(hits)
print('byte@418', raw[418])