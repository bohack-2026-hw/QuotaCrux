import sys, time, random, math

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    if not data:return
    n,m=data[:2]
    initial=[data[2+i*(n//m):2+(i+1)*(n//m)] for i in range(m)]
    rng=random.Random(17731+sum((i+1)*v for i,v in enumerate(data[2:])))
    start=time.perf_counter()
    best_cost=10**9
    best=None
    def solve(tol,mode,hw,noise,plan=None,mutation=None,limit=10**9):
        stacks=[s[:] for s in initial]
        loc=[0]*(n+1)
        mins=[min(s,default=n+1) for s in stacks]
        for i,s in enumerate(stacks):
            for x in s:loc[x]=i
        cost=0;ops=[];decisions={}
        for v in range(1,n+1):
            src=loc[v];s=stacks[src];p=s.index(v)
            while len(s)>p+1:
                end=len(s);key=(v,s[-1]);old=plan.get(key) if plan else None
                force=mutation is not None and key==mutation[0]
                cut=-1;bd=-1
                if old is not None and not force:
                    bottom,dst=old
                    if dst!=src:
                        try:
                            q=s.index(bottom,p+1)
                            cut=q;bd=dst
                        except ValueError:pass
                if cut<0:
                    tt=tol
                    if force:tt=rng.choice((0,0,5,10,20,40,80,n))
                    cut=end-1;mx=s[cut]
                    if tt>=n:cut=p+1
                    else:
                        while cut>p+1 and s[cut-1]+tt>=mx:
                            cut-=1
                            if s[cut]>mx:mx=s[cut]
                    if force and rng.random()<0.2:cut=rng.randrange(p+1,end)
                    block=s[cut:];mx=max(block);mn=min(block)
                    pivot=mx if mode==0 else mn if mode==1 else (mx+mn)*0.5
                    opts=[]
                    for d in range(m):
                        if d==src:continue
                        md=mins[d]
                        z=(md-pivot)*0.08 if md>=pivot else 100+pivot-md
                        z+=hw*len(stacks[d])
                        if noise:z+=rng.random()*noise
                        opts.append((z,d))
                    opts.sort()
                    if force:
                        r=rng.random()
                        rank=0 if r<0.38 else 1 if r<0.7 else 2 if r<0.87 else rng.randrange(len(opts))
                        bd=opts[min(rank,len(opts)-1)][1]
                    else:bd=opts[0][1]
                block=s[cut:]
                cost+=len(block)+1
                if cost>limit:return None
                decisions[key]=(block[0],bd)
                ops.append((block[0],bd+1))
                stacks[bd].extend(block);mins[bd]=min(mins[bd],min(block))
                for x in block:loc[x]=bd
                del s[cut:]
            s.pop();mins[src]=min(s,default=n+1);ops.append((v,0))
        return (cost,ops,decisions,(tol,mode,hw))
    for tol in (n,0,10,30,60):
        for mode in (0,1,2):
            for hw in (0.0,0.3,1.0):
                res=solve(tol,mode,hw,0,limit=best_cost)
                if res and res[0]<best_cost:best=res;best_cost=res[0]
    count=0
    while time.perf_counter()-start<0.48 and count<130:
        res=solve(rng.choice((0,0,5,10,20,40,80,n)),rng.randrange(3),rng.choice((0,0.1,0.3,0.6,1,2)),rng.choice((1,3,8,15)),limit=best_cost)
        if res and res[0]<best_cost:best=res;best_cost=res[0]
        count+=1
    cur=best;count=0
    while time.perf_counter()-start<1.72:
        if not cur[2]:break
        if count%60==0:cur=best
        keys=list(cur[2]);key=rng.choice(keys)
        elapsed=time.perf_counter()-start
        temp=max(0.5,6*(1-(elapsed-0.48)/1.24))
        allowance=-temp*math.log(max(1e-10,rng.random()))
        tol,mode,hw=cur[3]
        if rng.random()<0.08:tol=rng.choice((0,5,10,20,40,n))
        res=solve(tol,mode,hw,0,cur[2],(key,),cur[0]+allowance)
        if res:
            cur=res
            if res[0]<best_cost:best=res;best_cost=res[0]
        count+=1
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in best[1])+'\n')
if __name__=='__main__':main()
