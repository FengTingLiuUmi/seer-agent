import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\Login.swf')[0]
print('abc len', len(raw))
r = R(raw)
print('ver', r.u16(), r.u16(), 'p', r.p)
n = r.u30(); print('ints', n); [r.s32() for _ in range(max(0, n-1))]; print('p', r.p)
n = r.u30(); print('uints', n); [r.u32() for _ in range(max(0, n-1))]; print('p', r.p)
n = r.u30(); print('dbls', n); [r.d64() for _ in range(max(0, n-1))]; print('p', r.p)
n = r.u30(); print('strs', n)
for i in range(max(0, n-1)): r.raw(r.u30())
print('p', r.p)
n = r.u30(); print('nss', n)
for _ in range(max(0, n-1)): r.u8(); r.u30()
print('p', r.p)
n = r.u30(); print('nssets', n)
for _ in range(max(0, n-1)):
    c = r.u30()
    for _ in range(c): r.u30()
print('p', r.p)
n = r.u30(); print('mns', n)
import collections
kinds = collections.Counter()
for i in range(max(0, n-1)):
    k = r.u8(); kinds[hex(k)] += 1
    if k in (0x07, 0x0d): r.u30(); r.u30()
    elif k in (0x0f, 0x10): r.u30()
    elif k in (0x11, 0x12): pass
    elif k in (0x09, 0x0e): r.u30(); r.u30()
    elif k in (0x1b, 0x1c): r.u30()
    elif k == 0x1d:
        r.u30(); c = r.u30()
        for _ in range(c): r.u30()
    else:
        print('bad mn kind', hex(k), 'i', i, 'p', r.p); break
print('p', r.p, dict(kinds))
n = r.u30(); print('methods', n, 'at', r.p)
for i in range(max(0, n-1)):
    pc = r.u30(); rt = r.u30()
    for _ in range(pc): r.u30()
    r.u30(); fl = r.u8()
    if fl & 0x08:
        oc = r.u30()
        for _ in range(oc): r.u30(); r.u8()
print('p', r.p)
n = r.u30(); print('metadata', n, 'at', r.p, 'p now', r.p)
for _ in range(max(0, n-1)):
    r.u30(); c = r.u30()
    for _ in range(c): r.u30(); r.u30()
print('p', r.p)
n = r.u30(); print('instances', n, 'at', r.p)
print('next bytes', raw[r.p:r.p+12].hex(' '))