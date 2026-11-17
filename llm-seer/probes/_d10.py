import sys
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\Client.swf')[0]
TARGET = 49


def u30(d, p):
    r = 0
    for i in range(4):
        b = d[p]; p += 1
        if i < 3:
            r |= (b & 0x7f) << (7 * i)
            if not b & 0x80: return r, p
        else: return r | (b << 21), p


res = []
for start in range(4, 8):
    for k1 in (1, 2):
        for n1 in range(0, 9):
            p1 = start
            c1, p2 = u30(raw, p1)
            body1 = 4 * n1
            p3 = p2 + body1
            if p3 > TARGET: continue
            for k2 in (1, 2):
                for n2 in range(0, 9):
                    q1 = p3
                    c2, q2 = u30(raw, q1)
                    p4 = q2 + 4 * n2
                    if p4 > TARGET: continue
                    for n3 in range(0, 9):
                        c3, r2 = u30(raw, p4)
                        if r2 + 8 * n3 == TARGET:
                            res.append((start, n1, c1, n2, c2, n3, c3))
print(res)