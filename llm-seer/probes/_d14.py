import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\Client.swf')[0]
r = R(raw, 49)


def u(): return r.u30()


n = u()
for _ in range(n - 1): r.raw(r.u30())
n = u()
for _ in range(n - 1): r.u8(); r.u30()
n = u()
for _ in range(n - 1):
    c = u()
    for _ in range(c): u()
n = u()
for _ in range(n - 1):
    k = r.u8()
    if k in (0x07, 0x0d): u(); u()
    elif k in (0x0f, 0x10): u()
    elif k in (0x11, 0x12): pass
    elif k in (0x09, 0x0e): u(); u()
    elif k in (0x1b, 0x1c): u()
    elif k == 0x1d:
        u(); c = u()
        for _ in range(c): u()
nmeth = u(); print('methods count', nmeth, 'at', r.p)
for i in range(nmeth - 1):
    pc = u(); rt = u()
    for _ in range(pc): u()
    nm = u(); fl = r.u8()
    if fl & 0x08:
        oc = u()
        for _ in range(oc): u(); r.u8()
print('after methods p', r.p)
nmet = u(); print('metadata count', nmet, 'at', r.p)
for _ in range(nmet - 1):
    u(); c = u()
    for _ in range(c): u(); u()
print('after metadata p', r.p)
ninst = u(); print('instances count', ninst, 'at', r.p)
print('next:', raw[r.p:r.p+8].hex(' '))