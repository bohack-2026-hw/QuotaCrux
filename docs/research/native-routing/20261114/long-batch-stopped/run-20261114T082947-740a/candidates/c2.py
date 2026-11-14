import sys, random, time

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    n,m=data[:2]
    initial=[data[2+i*(n//m):2+(i+1)*(n//m)] for i in range(m)]
    start=time.perf_counter()
    deadline=start+1.65
    rng=random.Random(20261114)
    def baseline():
        s=[a[:] for a in initial]; ops=[]; cost=0
        for v in range(1,n+1):
            src=next(i for i,a in enumerate(s) if v in a)
            p=s[src].index(v)+1
            if p<len(s[src]):
                d=min((i for i in range(m) if i!=src),key=lambda i:len(s[i]))
                group=s[src][p:]; del s[src][p:]; s[d].extend(group)
                ops.append((group[0],d+1)); cost+=len(group)+1
            s[src].pop(); ops.append((v,0))
        return cost,ops
    best,bestops=baseline()
    run=0
    while time.perf_counter()<deadline:
        s=[a[:] for a in initial]
        loc=[0]*(n+1)
        for i,a in enumerate(s):
            for x in a:loc[x]=i
        mins=[min(a) if a else n+1 for a in s]
        ops=[]; cost=0
        mode=run%6
        noise=0 if run<6 else rng.choice([0,2,5,10,20,35])
        maxrun=rng.choice([n,n,n,n,2,3,4,6,10]) if run>=6 else n
        for v in range(1,n+1):
            src=loc[v]; a=s[src]; p=a.index(v)+1
            while len(a)>p:
                end=len(a); j=end-1
                while j>p and a[j-1]>a[j] and end-j<maxrun:j-=1
                bottom=a[j]
                if mode in (0,1,2):
                    good=[i for i in range(m) if i!=src and mins[i]>bottom]
                    if good:
                        d=min(good,key=lambda i:mins[i]+noise*rng.random())
                    else:
                        d=max((i for i in range(m) if i!=src),key=lambda i:mins[i]+noise*rng.random())
                    if mode==1 and mins[d]<bottom:
                        while j<end-1 and a[j]>mins[d]:j+=1
                else:
                    top=a[-1]
                    good=[i for i in range(m) if i!=src and mins[i]>top]
                    if good:
                        d=min(good,key=lambda i:mins[i]+noise*rng.random())
                        while j<end-1 and a[j]>mins[d]:j+=1
                    else:
                        d=max((i for i in range(m) if i!=src),key=lambda i:mins[i]+noise*rng.random())
                    if mode==5 and end-p>1 and mins[d]<a[-1]:j=p
                if mode==2 and j>p and rng.random()<0.18:j=p
                group=a[j:]; del a[j:]; s[d].extend(group)
                for x in group:loc[x]=d
                mins[d]=min(mins[d],min(group))
                ops.append((group[0],d+1)); cost+=len(group)+1
                if cost>=best:break
            if cost>=best:break
            a.pop(); ops.append((v,0)); mins[src]=min(a) if a else n+1
        else:
            if cost<best and len(ops)<=5000:best,bestops=cost,ops
        run+=1
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in bestops))

main()
