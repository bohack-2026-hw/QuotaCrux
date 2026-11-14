import sys, random, time, math

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    n,m=data[:2]
    initial=[data[2+i*(n//m):2+(i+1)*(n//m)] for i in range(m)]
    start=time.perf_counter(); deadline=start+1.73
    rng=random.Random(20261114)
    def simulate(ref=None, mutate=None, mode=0, noise=0):
        s=[a[:] for a in initial]
        loc=[0]*(n+1)
        for i,a in enumerate(s):
            for x in a:loc[x]=i
        mins=[min(a) if a else n+1 for a in s]
        ops=[]; path=[]; policy={}; cost=0
        for v in range(1,n+1):
            src=loc[v]; a=s[src]; p=a.index(v)+1
            while len(a)>p:
                end=len(a); top=a[-1]; key=v*(n+1)+top
                j=end-1
                while j>p and a[j-1]>a[j]:j-=1
                lo=j
                old=ref.get(key) if ref is not None else None
                use_old=False
                if old is not None and key!=mutate:
                    b,d=old
                    if d!=src and b in a[p:]:
                        j=a.index(b,p); use_old=True
                if not use_old:
                    if key==mutate:
                        # Diverse local moves: other destinations, split or join segments.
                        if rng.random()<0.72:
                            ds=[i for i in range(m) if i!=src]
                            ds.sort(key=lambda i:(0,mins[i]-top) if mins[i]>top else (1,-mins[i]))
                            d=ds[min(len(ds)-1,int(rng.expovariate(0.45)))]
                        else:
                            d=rng.randrange(m-1)
                            if d>=src:d+=1
                        r=rng.random()
                        if r<0.55:
                            j=lo
                            while j<end-1 and a[j]>mins[d]:j+=1
                        elif r<0.72:j=lo
                        elif r<0.85:j=p
                        elif r<0.94:j=end-1
                        else:j=rng.randrange(p,end)
                    elif mode in (0,1,2):
                        good=[i for i in range(m) if i!=src and mins[i]>a[j]]
                        if good:d=min(good,key=lambda i:mins[i]+noise*rng.random())
                        else:d=max((i for i in range(m) if i!=src),key=lambda i:mins[i]+noise*rng.random())
                        if mode==1 and mins[d]<a[j]:
                            while j<end-1 and a[j]>mins[d]:j+=1
                        if mode==2 and j>p and rng.random()<0.18:j=p
                    else:
                        good=[i for i in range(m) if i!=src and mins[i]>top]
                        if good:
                            d=min(good,key=lambda i:mins[i]+noise*rng.random())
                            while j<end-1 and a[j]>mins[d]:j+=1
                        else:d=max((i for i in range(m) if i!=src),key=lambda i:mins[i]+noise*rng.random())
                        if mode==5 and end-p>1 and mins[d]<top:j=p
                group=a[j:]; del a[j:]; s[d].extend(group)
                for x in group:loc[x]=d
                mins[d]=min(mins[d],min(group))
                ops.append((group[0],d+1)); cost+=len(group)+1
                path.append((key,group[0],d)); policy[key]=(group[0],d)
                if cost>1800:return cost,None,None,None
            a.pop(); ops.append((v,0)); mins[src]=min(a) if a else n+1
        return cost,ops,path,policy
    best=10**9; bestops=None; bestpath=None; bestpolicy=None
    run=0
    while run<12 or time.perf_counter()<start+0.30:
        result=simulate(mode=run%6,noise=0 if run<6 else rng.choice([0,2,5,10,20,35]))
        cost,ops,path,policy=result
        if ops is not None and cost<best:
            best,bestops,bestpath,bestpolicy=result
        run+=1
    current=best; curpath=bestpath; curpolicy=bestpolicy
    it=0
    while time.perf_counter()<deadline:
        if not curpath:break
        key=curpath[rng.randrange(len(curpath))][0]
        result=simulate(curpolicy,key,mode=rng.choice([0,1,3,4]),noise=rng.choice([0,0,3,8]))
        cost,ops,path,policy=result
        progress=(time.perf_counter()-start)/1.73
        temp=0.6+3.0*(1-progress)
        if ops is not None:
            if cost<best:
                best,bestops,bestpath,bestpolicy=result
            if cost<=current or rng.random()<math.exp(min(0,(current-cost)/temp)):
                current=cost; curpath=path; curpolicy=policy
        it+=1
        if it%100==0:
            current=best;curpath=bestpath;curpolicy=bestpolicy
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in bestops))

main()
