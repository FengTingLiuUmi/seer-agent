import sys, re
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')[1]
r = R(raw)
print('ver', r.u16(), r.u16())
for i in range(3):
    n = r.u30(); print(['int', 'uint', 'dbl'][i], n)
    for _ in range(max(0, n - 1)):
        (r.s32 if i == 0 else (r.u32 if i == 1 else r.d64))()
n = r.u30(); print('strs', n, 'at', r.p)
strs = [None]
for _ in range(max(0, n - 1)):
    strs.append(r.raw(r.u30()).decode('utf-8', 'replace'))
print('after strs p', r.p, 'sample', strs[1:4], strs[-2:])
n = r.u30(); print('ns', n)
nss = [None]
for _ in range(max(0, n - 1)):
    nss.append((r.u8(), r.u30()))
n = r.u30(); print('nssets', n)
for _ in range(max(0, n - 1)):
    c = r.u30()
    for _ in range(c): r.u30()
n = r.u30(); print('mns', n)
mns = [None]
for _ in range(max(0, n - 1)):
    k = r.u8(); e = [k]
    if k in (0x07, 0x0d): e += [r.u30(), r.u30()]
    elif k in (0x0f, 0x10): e += [r.u30()]
    elif k in (0x11, 0x12): pass
    elif k in (0x09, 0x0e): e += [r.u30(), r.u30()]
    elif k in (0x1b, 0x1c): e += [r.u30()]
    elif k == 0x1d:
        e += [r.u30()]; c = r.u30(); e += [r.u30() for _ in range(c)]
    else: raise SystemExit('mn kind %x at %d' % (k, r.p))
    mns.append(e)
print('after mns p', r.p)
open('dll_block1_strings.txt', 'w', encoding='utf-8').write('\n'.join(
    '%d\t%s' % (i, s) for i, s in enumerate(strs) if s is not None))
kw = re.compile(r'Head|Encrypt|Decrypt|LEN|head|headInfo|cmd|Cmd|token|TOKEN|key|KEY|MIDLLE|HEX', re.I)
hits = [s for s in strs if s and kw.search(s)]
print('kw strings', len(hits))
print(hits[:60])