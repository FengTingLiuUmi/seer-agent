import sys, traceback
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import abcadis as A

abcs = A.read_swf('TaomeeLibraryDLL.dec.swf')
for i, (raw, fl) in enumerate(abcs):
    try:
        a = A.ABC(raw)
    except Exception as e:
        print('FAIL block', i, 'len', len(raw), 'pos', getattr(e, 'pos', '?'), repr(e)[:80])
        # instrumented re-parse
        r = A.R(raw)
        try:
            print('  minor/major', r.u16(), r.u16(), 'pos', r.p)
            break
        except Exception:
            pass
    else:
        print('ok block', i, len(raw), 'inst', len(a.instances), 'scripts', len(a.scripts), 'bodies', len(a.bodies))
        if i > 3: break
