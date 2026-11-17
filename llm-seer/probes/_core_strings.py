import re
d=open('RobotCoreDLL.dec.swf','rb').read()
s=[x.decode() for x in re.findall(rb'[\x20-\x7e]{4,}',d)]
print('strings',len(s))
def hits(*pats):
    out=[]
    for x in s:
        if any(p in x for p in pats): out.append(x)
    return sorted(set(out))[:12]
for p in ('LOGIN_IN','enterGame','SocketConnection','CommandID','getCmdLabel','cmdID','EnterGame','socket'):
    print('==',p,'->',hits(p))
