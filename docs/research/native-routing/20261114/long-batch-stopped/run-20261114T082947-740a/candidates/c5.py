import sys, random, time, math

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    n,m=data[:2]; h=n//m
    initial=[data[2+i*h:2+(i+1)*h] for i in range(m)]
    start=time.perf_counter(); deadline=start+1.78
    rng=random.Random(20261114)
    initialloc=[0]*(n+1)
    for i,a in enumerate(initial):
        for x in a:initialloc[x]=i
    def simulate(ref=None, parent=None, cache=None, change=-1, mode=0, noise=0, limit=100000):
        if change>=0:
            cs,cl,cm=cache[change]
            s=[a[:] for a in cs]; loc=cl[:]; mins=cm[:]
            ent=parent[2][change]; idx=ent[3]; cost=ent[4]; first=ent[5]
            ops=parent[1][:idx]; path=parent[2][:change]
        else:
            s=[a[:] for a in initial];loc=initialloc[:]
            mins=[min(a) if a else n+1 for a in s]
            cost=0;ops=[];path=[];first=1
        mutated=False
        for v in range(first,n+1):
            src=loc[v];a=s[src];p=a.index(v)+1
            while len(a)>p:
                end=len(a);top=a[-1];key=v*(n+1)+top
                j=end-1
                while j>p and a[j-1]>a[j]:j-=1
                lo=j
                old=ref.get(key) if ref is not None else None
                force=change>=0 and not mutated
                use_old=False
                if old is not None and not force:
                    b,d=old
                    if d!=src and loc[b]==src:
                        try:
                            j=a.index(b,p);use_old=True
                        except ValueError:pass
                if not use_old:
                    if force:
                        mutated=True
                        ds=[i for i in range(m) if i!=src]
                        ds.sort(key=lambda i:(0,mins[i]-top) if mins[i]>top else (1,-mins[i]))
                        for attempt in range(4):
                            if rng.random()<0.85:d=ds[min(len(ds)-1,int(rng.expovariate(0.55)))]
                            else:d=rng.choice(ds)
                            r=rng.random()
                            if r<0.48:
                                j=lo
                                while j<end-1 and a[j]>mins[d]:j+=1
                            elif r<0.69:j=lo
                            elif r<0.87:j=p
                            elif r<0.94:j=end-1
                            else:j=rng.randrange(p,end)
                            if old!=(a[j],d):break
                        if old==(a[j],d):
                            d=(d+1)%m
                            if d==src:d=(d+1)%m
                    elif mode==6:
                        d=min((i for i in range(m) if i!=src),key=lambda i:len(s[i]));j=p
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
                group=a[j:];del a[j:];s[d].extend(group)
                for x in group:loc[x]=d
                mins[d]=min(mins[d],min(group))
                path.append((key,group[0],d,len(ops),cost,v))
                ops.append((group[0],d+1));cost+=len(group)+1
                if cost>limit:return cost,None,None
            a.pop();ops.append((v,0));mins[src]=min(a) if a else n+1
        return cost,ops,path
    def prepare(result):
        s=[a[:] for a in initial];loc=initialloc[:]
        mins=[min(a) if a else n+1 for a in s]
        cache=[]
        for b,d1 in result[1]:
            src=loc[b];a=s[src]
            if d1==0:
                s[src]=a[:-1]
                mins[src]=min(s[src]) if s[src] else n+1
            else:
                cache.append((s[:],loc[:],mins[:]))
                d=d1-1;j=a.index(b);group=a[j:]
                s[src]=a[:j];s[d]=s[d]+group
                for x in group:loc[x]=d
                mins[src]=min(s[src]) if s[src] else n+1
                mins[d]=min(mins[d],min(group))
        policy={ent[0]:(ent[1],ent[2]) for ent in result[2]}
        return cache,policy
    bestresult=simulate(mode=6);best=bestresult[0];run=0
    while run<12 or time.perf_counter()<start+0.13:
        result=simulate(mode=run%6,noise=0 if run<6 else rng.choice([0,2,5,10,20,35]),limit=best)
        if result[1] is not None and result[0]<best:best=result[0];bestresult=result
        run+=1
    current=bestresult;cache,policy=prepare(current);it=0
    while time.perf_counter()<deadline:
        if not current[2]:break
        change=rng.randrange(len(current[2]))
        result=simulate(policy,current,cache,change,mode=rng.choice([0,1,3,4]),noise=rng.choice([0,0,3,8]),limit=current[0]+35)
        cost=result[0]
        progress=(time.perf_counter()-start)/1.78
        temp=0.45+2.5*(1-progress)
        if result[1] is not None:
            if cost<best:best=cost;bestresult=result
            if cost<=current[0] or rng.random()<math.exp(min(0,(current[0]-cost)/temp)):
                current=result;cache,policy=prepare(current)
        it+=1
        if it%180==0:
            current=bestresult;cache,policy=prepare(current)
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in bestresult[1]))

main()
