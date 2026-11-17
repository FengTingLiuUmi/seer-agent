import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\Login.swf')[0]
TARGET = 1216


def u30(d, p):
    r = 0
    for i in range(4):
        b = d[p]; p += 1
        if i < 3:
            r |= (b & 0x7f) << (7 * i)
            if not b & 0x80: return r, p
        else: return r | (b << 21), p


int_c, p = u30(raw, 4)
print('int count read', int_c, 'p', p)
best = []
for dummy1 in (0, 1):
    for n1 in range(0, int_c + 2):
        if int_c - n1 != dummy1: continue
        p1 = p + 4 * n1
        if p1 > TARGET: break
        for uc, k2 in ((u30(raw, p1)[0], 1),):
            p2 = u30(raw, p1)[1]
            for dummy2 in (0, 1):
                n2 = uc - dummy2
                if n2 < 0: continue
                q = p2 + 4 * n2
                if q > TARGET: continue
                dc, q2 = u30(raw, q)
                for dummy3 in (0, 1):
                    n3 = dc - dummy3
                    if n3 < 0: continue
                    if q2 + 8 * n3 == TARGET:
                        best.append((n1, int_c, n2, uc, n3, dc))
print(best)