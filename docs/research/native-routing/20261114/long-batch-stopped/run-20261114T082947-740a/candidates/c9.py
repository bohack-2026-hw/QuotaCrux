import sys, random, time, math

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    n,m=data[:2];h=n//m
    initial=[data[2+i*h:2+(i+1)*h] for i in range(m)]
    start=time.perf_counter();deadline=start+1.79
    rng=random.Random(20261114)
    iloc=[0]*(n+1)
    for i,a in enumerate(initial):
        for x in a:iloc[x]=i

    def prepare(result):
        s=initial;loc=iloc[:];states=[]
        vs=[None]*(n+2);oi=[0]*(n+2);pi=[0]*(n+2);pc=[0]*(n+2)
        vs[1]=s;cost=0;nm=0
        for k,(b,d1) in enumerate(result[1]):
            src=loc[b];a=s[src];s=s[:]
            if d1==0:
                s[src]=a[:-1]
                vs[b+1]=s;oi[b+1]=k+1;pi[b+1]=nm;pc[b+1]=cost
            else:
                states.append(s[:]);d=d1-1;j=a.index(b);g=a[j:]
                s[src]=a[:j];s[d]=s[d]+g
                for x in g:loc[x]=d
                cost+=len(g)+1;nm+=1
        policy={e[0]:(e[1],e[2]) for e in result[2]}
        seen={};nxt={}
        for k in range(len(result[2])-1,-1,-1):
            e=result[2][k];b=e[1]
            if b in seen and seen[b]!=e[2]:nxt[k]=(b,seen[b])
            seen[b]=e[2]
        return states,vs,oi,pi,pc,policy,nxt

    def simulate(parent=None,cache=None,change=-1,override=None,mode=0,noise=0,limit=10**9):
        if change>=0:
            e=parent[2][change];first=e[5];cost=e[4]
            s=[a[:] for a in cache[0][change]]
            loc=iloc[:]
            for i,a in enumerate(s):
                for x in a:loc[x]=i
            ops=parent[1][:e[3]];path=parent[2][:change]
            ref=cache[5]
        else:
            s=[a[:] for a in initial];loc=iloc[:];first=1;cost=0;ops=[];path=[];ref=None
        mins=[min(a) if a else n+1 for a in s]
        mutated=False
        for v in range(first,n+1):
            if change>=0 and v>first and s==cache[1][v]:
                total=parent[0]+cost-cache[4][v]
                if total>limit:return total,None,None,0
                return total,ops,path,v
            src=loc[v];a=s[src];p=a.index(v)+1
            while len(a)>p:
                end=len(a);top=a[-1];key=v*(n+1)+top
                old=ref.get(key) if ref is not None else None
                force=change>=0 and not mutated
                use_old=False
                if old is not None and not force:
                    b,d=old
                    if d!=src:
                        try:j=a.index(b,p);use_old=True
                        except ValueError:pass
                if not use_old:
                    j=end-1
                    while j>p and a[j-1]>a[j]:j-=1
                    lo=j
                    if force:
                        mutated=True
                        if override is not None and override[1]!=src and override[0] in a[p:]:
                            b,d=override;j=a.index(b,p)
                        else:
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
                        if good:
                            if noise:d=min(good,key=lambda i:mins[i]+noise*rng.random())
                            else:d=min(good,key=mins.__getitem__)
                        else:
                            if noise:d=max((i for i in range(m) if i!=src),key=lambda i:mins[i]+noise*rng.random())
                            else:d=max((i for i in range(m) if i!=src),key=mins.__getitem__)
                        if mode==1 and mins[d]<a[j]:
                            while j<end-1 and a[j]>mins[d]:j+=1
                        if mode==2 and j>p and rng.random()<0.18:j=p
                    else:
                        good=[i for i in range(m) if i!=src and mins[i]>top]
                        if good:
                            if noise:d=min(good,key=lambda i:mins[i]+noise*rng.random())
                            else:d=min(good,key=mins.__getitem__)
                            while j<end-1 and a[j]>mins[d]:j+=1
                        else:
                            if noise:d=max((i for i in range(m) if i!=src),key=lambda i:mins[i]+noise*rng.random())
                            else:d=max((i for i in range(m) if i!=src),key=mins.__getitem__)
                        if mode==5 and end-p>1 and mins[d]<top:j=p
                group=a[j:];del a[j:];s[d].extend(group)
                for x in group:loc[x]=d
                mins[d]=min(mins[d],min(group))
                path.append((key,group[0],d,len(ops),cost,v))
                ops.append((group[0],d+1));cost+=len(group)+1
                if cost>limit or len(ops)>5000:return cost,None,None,0
            a.pop();ops.append((v,0));mins[src]=min(a) if a else n+1
        if len(ops)>5000:return cost,None,None,0
        return cost,ops,path,0

    def materialize(result,parent,cache):
        cost,ops,path,v=result
        if v:
            opdelta=len(ops)-cache[2][v];cdelta=cost-parent[0]
            ops=ops+parent[1][cache[2][v]:]
            path=path+[(e[0],e[1],e[2],e[3]+opdelta,e[4]+cdelta,e[5]) for e in parent[2][cache[3][v]:]]
        return cost,ops,path,0

    bestresult=simulate(mode=6);best=bestresult[0];run=0
    while run<12 or time.perf_counter()<start+0.13:
        result=simulate(mode=run%6,noise=0 if run<6 else rng.choice([0,2,5,10,20,35]),limit=best)
        if result[1] is not None and result[0]<best:best=result[0];bestresult=result
        run+=1
    current=bestresult;cache=prepare(current);it=0
    while time.perf_counter()<deadline:
        path=current[2]
        if not path:break
        change=rng.randrange(len(path));override=None;nxt=cache[6]
        if rng.random()<0.48 and nxt:
            change=rng.choice(list(nxt));override=nxt[change]
        elif rng.random()<0.5:
            for _ in range(3):
                k=(path[change+1][4] if change+1<len(path) else current[0])-path[change][4]
                if k>2:break
                change=rng.randrange(len(path))
        result=simulate(current,cache,change,override,mode=rng.choice([0,1,3,4]),noise=rng.choice([0,0,3,8]),limit=current[0]+25)
        cost=result[0];progress=(time.perf_counter()-start)/1.79
        temp=0.25+1.65*(1-progress)
        if result[1] is not None and (cost<=current[0] or rng.random()<math.exp(min(0,(current[0]-cost)/temp))):
            result=materialize(result,current,cache)
            if len(result[1])<=5000:
                current=result;cache=prepare(current)
                if cost<best:best=cost;bestresult=result
        it+=1
        if it%140==0:current=bestresult;cache=prepare(current)
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in bestresult[1]))

main()
