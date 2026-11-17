import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

blk = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')[0]
r = R(blk)
r.u16(); r.u16()
for i in range(3):
    n = r.u30()
    for _ in range(max(0, n - 1)):
        (r.s32 if i == 0 else (r.u32 if i == 1 else r.d64))()
n = r.u30(); strs = [None]
for _ in range(max(0, n - 1)): strs.append(r.raw(r.u30()).decode('utf-8', 'replace'))
print('strs:')
for i, s in enumerate(strs): print(' %2d %r' % (i, s))
n = r.u30(); nss = [None]
for _ in range(max(0, n - 1)): nss.append((r.u8(), r.u30()))
print('nss:', [(i, nss[i][0], strs[nss[i][1]] if nss[i][1] < len(strs) else nss[i][1]) for i in range(1, len(nss))])
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
    mns.append(e)
print('mns:', [(i, hex(e[0]), strs[e[2]] if len(e) > 2 and e[2] < len(strs) else '') for i, e in enumerate(mns) if i])
print('p after mns', r.p)
print('bytes 376..%d:' % len(blk))
print(' '.join('%d:%02x' % (i, blk[i]) for i in range(376, len(blk))))