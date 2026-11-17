import sys, itertools
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

b = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')


def parse(raw, dI, dS, dB, dM, report=False):
    r = R(raw)
    r.u16(); r.u16()
    for cnt in range(3):
        n = r.u30()
        for _ in range(max(0, n - 1)): r.s32() if cnt == 0 else (r.u32() if cnt == 1 else r.d64())
    n = r.u30()
    for _ in range(max(0, n - 1)): r.raw(r.u30())
    n = r.u30()
    for _ in range(max(0, n - 1)): r.u8(); r.u30()
    n = r.u30()
    for _ in range(max(0, n - 1)):
        c = r.u30()
        for _ in range(c): r.u30()
    n = r.u30()
    for _ in range(max(0, n - 1)):
        k = r.u8()
        if k in (0x07, 0x0d): r.u30(); r.u30()
        elif k in (0x0f, 0x10): r.u30()
        elif k in (0x11, 0x12): pass
        elif k in (0x09, 0x0e): r.u30(); r.u30()
        elif k in (0x1b, 0x1c): r.u30()
        elif k == 0x1d:
            r.u30(); c = r.u30()
            for _ in range(c): r.u30()
    n = r.u30()
    for _ in range(max(0, n - dM)):
        r.u30(); c = r.u30()
        for _ in range(c): r.u30(); r.u30()

    def traits():
        n = r.u30()
        for _ in range(n):
            r.u30(); k = r.u8(); base = k & 0x0f
            if base in (0, 6):
                r.u30(); r.u30(); vi = r.u30()
                if vi: r.u8()
            elif base in (1, 2, 3): r.u30(); r.u30()
            elif base == 4: r.u30(); r.u30()
            elif base == 5: r.u30(); r.u30()
            if k & 0x40:
                c = r.u30()
                for _ in range(c): r.u30()

    n = r.u30()
    for _ in range(max(0, n - dI)):
        r.u30(); r.u30(); fl = r.u8()
        if fl & 0x08: r.u30()
        c = r.u30()
        for _ in range(c): r.u30()
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dI)):
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dS)):
        r.u30(); traits()
    n = r.u30()
    for _ in range(max(0, n - dB)):
        r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
        cl = r.u30(); r.raw(cl)
        ec = r.u30()
        for _ in range(ec):
            for _ in range(5): r.u30()
        traits()
    return r.p


fails = [i for i, raw in enumerate(b) if not _ok(raw)] if False else None
for i, raw in enumerate(b):
    try:
        avm2.ABC(raw); continue
    except Exception:
        pass
    hit = None
    for combo in itertools.product([0, 1], repeat=4):
        try:
            p = parse(raw, *combo)
        except Exception:
            continue
        if p == len(raw): hit = combo
    print('block', i, 'len', len(raw), 'exact combos', hit)
    if i > 4: break