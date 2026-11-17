import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

b = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')
raw = b[0]
r = R(raw)
r.u16(); r.u16()
for cnt in range(3):
    n = r.u30()
    for _ in range(max(0, n-1)): r.s32() if cnt == 0 else (r.u32() if cnt == 1 else r.d64())
n = r.u30()
for _ in range(max(0, n-1)): r.raw(r.u30())
n = r.u30()
for _ in range(max(0, n-1)): r.u8(); r.u30()
n = r.u30()
for _ in range(max(0, n-1)):
    c = r.u30()
    for _ in range(c): r.u30()
n = r.u30()
for _ in range(max(0, n-1)):
    k = r.u8()
    if k in (0x07, 0x0d): r.u30(); r.u30()
    elif k in (0x0f, 0x10): r.u30()
    elif k in (0x11, 0x12): pass
    elif k in (0x09, 0x0e): r.u30(); r.u30()
    elif k in (0x1b, 0x1c): r.u30()
    elif k == 0x1d:
        r.u30(); c = r.u30()
        for _ in range(c): r.u30()
print('pools ok, p', r.p)

n = r.u30(); print('method count field', n, 'at', r.p)
for i in range(max(0, n-1)):
    print('  method', i, 'at', r.p)
    pc = r.u30(); rt = r.u30()
    for _ in range(pc): r.u30()
    nm = r.u30(); fl = r.u8()
    print('    params', pc, 'name', nm, 'flags', hex(fl))
    if fl & 0x08:
        oc = r.u30()
        for _ in range(oc): r.u30(); r.u8()
print('methods end p', r.p, 'len', len(raw))
n = r.u30(); print('metadata count', n, 'at', r.p, 'end p', r.p)
assert abs(r.p - len(raw)) < 60