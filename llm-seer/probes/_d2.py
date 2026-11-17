import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

b = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')
raw = b[0]
print('len', len(raw), raw[:16].hex(' '))
r = R(raw)
print('maj/min', r.u16(), r.u16(), 'p', r.p)
n = r.u30(); print('int count', n)
for _ in range(max(0, n-1)): r.s32()
print('p', r.p)
n = r.u30(); print('uint count', n)
for _ in range(max(0, n-1)): r.u32()
print('p', r.p)
n = r.u30(); print('dbl count', n)
for _ in range(max(0, n-1)): r.d64()
print('p', r.p)
n = r.u30(); print('str count', n)
try:
    for i in range(max(0, n-1)):
        L = r.u30(); s = r.raw(L)
        if i < 4: print('  str', i, L, s[:40])
except Exception as e:
    print('strfail at', r.p, repr(e), 'count so far')
print('p', r.p)
n = r.u30(); print('ns count', n)
for _ in range(max(0, n-1)): r.u8(); r.u30()
print('p', r.p)
n = r.u30(); print('nsset count', n)
for _ in range(max(0, n-1)):
    c = r.u30()
    for _ in range(c): r.u30()
print('p', r.p)
n = r.u30(); print('mn count', n)
import collections
kinds = collections.Counter()
for _ in range(max(0, n-1)):
    k = r.u8(); kinds[k] += 1
    if k in (0x07, 0x0d): r.u30(); r.u30()
    elif k in (0x0f, 0x10): r.u30()
    elif k in (0x11, 0x12): pass
    elif k in (0x09, 0x0e): r.u30(); r.u30()
    elif k in (0x1b, 0x1c): r.u30()
    elif k == 0x1d:
        r.u30(); c = r.u30()
        for _ in range(c): r.u30()
    else:
        print('  unusual mn kind', hex(k), 'at', r.p); raise SystemExit
print('p', r.p, dict(kinds))