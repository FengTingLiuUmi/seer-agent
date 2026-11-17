import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\Client.swf')[0]
r = R(raw)
print('ver', r.u16(), r.u16())
for name, reader in (('int', 's32'), ('uint', 'u32'), ('dbl', 'd64')):
    n = r.u30()
    print(name, 'count', n, 'at', r.p - len(bytearray()) )
    for _ in range(max(0, n - 1)): getattr(r, reader)()
    print('  p', r.p)
n = r.u30()
print('str count', n, 'at', r.p)
ss = []
for _ in range(max(0, n - 1)):
    L = r.u30(); ss.append(r.raw(L))
print('p', r.p, 'first strings', ss[:6])
n = r.u30(); print('ns count', n, 'at', r.p)
ns = []
for _ in range(max(0, n - 1)):
    k = r.u8(); v = r.u30(); ns.append((k, v))
print('p', r.p, 'ns sample', ns[:4])
print('strings by idx', [(i, ss[i - 1][:20] if 0 < i <= len(ss) else None) for k, v in ns[:4] for i in (v,)])