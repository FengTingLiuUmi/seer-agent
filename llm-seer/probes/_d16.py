import sys, re
sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\tools')
import avm2
from avm2 import R, ABC

raw = avm2.read_swf(r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-proto\TaomeeLibraryDLL.dec.swf')[1]
a = ABC.__new__(ABC)
try:
    ABC.__init__(a, raw)
except Exception as e:
    print('partial parse stopped at', repr(e)[:60], 'pos', getattr(a, '_p', '?'))
# pools are stored even on failure
print('strings', len(a.strs), 'mns', len(a.mns), 'methods', len(a.methods), 'instances', len(a.instances), 'bodies', len(a.bodies))
targets = ('SocketImpl', 'SocketEncryptImpl', 'MessageEncrypt', 'HeadInfo', 'PlayerKernel')
for ins in a.instances:
    nm = a.mn_(ins['name'])
    if not any(t in nm for t in targets): continue
    print('===', nm, '<-', a.mn_(ins['super']))
    for t in ins['traits']:
        k = {0: 'var', 1: 'fun', 2: 'get', 3: 'set', 4: 'class', 5: 'func', 6: 'const'}[t['kind']]
        print('  %-5s %-28s %s' % (k, a.s_(t['name']), t.get('method')))