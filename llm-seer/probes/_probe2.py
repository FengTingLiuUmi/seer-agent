import collections,math
d=open("TaomeeLibraryDLL.swf","rb").read(); n=len(d)
# longest runs
best=[]
i=0
while i<n:
    j=i
    while j+1<n and d[j+1]==d[i]: j+=1
    if j-i+1>=8: best.append((j-i+1,i,hex(d[i])))
    i=j+1
best.sort(reverse=True); print("runs>=8:",len(best),best[:6])
# index of coincidence for periods
def ioc(step):
    tot=0;c=0
    for o in range(step):
        s=d[o::step]; f=collections.Counter(s); m=len(s)
        if m<2: continue
        tot+=sum(v*(v-1) for v in f.values())/(m*(m-1)); c+=1
    return tot/c
base=1/256
top=sorted(((round(ioc(k),5),k) for k in range(1,65)),reverse=True)[:8]
print("IoC top(baseline .0039):",top)
# even/odd split check
print("IoC2:",round(ioc(2),5),"IoC4:",round(ioc(4),5),"IoC16:",round(ioc(16),5))
