import sys,time,random,math

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    if not data:return
    n,m=data[:2]
    initial=tuple(tuple(data[2+i*(n//m):2+(i+1)*(n//m)]) for i in range(m))
    rng=random.Random(17731+sum((i+1)*v for i,v in enumerate(data[2:])))
    start=time.perf_counter();empty=n+1
    def solve(params,noise=0,base=None,change=None,limit=100000):
        tol,mode,hw=params
        if base is None:
            stacks=list(initial);mins=[min(s,default=empty) for s in stacks]
            cost=0;ops=[];snaps=[];plan={};vstart=1;oldplan={}
        else:
            key,kind=change;vstart=key[0]
            ss,mm,cost,opidx=base[3][vstart-1]
            stacks=list(ss);mins=list(mm)
            ops=base[1][:opidx];snaps=base[3][:vstart-1]
            oldplan=base[2];plan={k:x for k,x in oldplan.items() if k[0]<vstart}
        loc=[0]*(n+1)
        for i,s in enumerate(stacks):
            for x in s:loc[x]=i
        extra=0
        for v in range(vstart,n+1):
            if base is not None and v>vstart:
                oldss,oldmm,oldcost,oldidx=base[3][v-1]
                if tuple(stacks)==oldss:
                    dc=cost-oldcost;di=len(ops)-oldidx
                    finalcost=base[0]+dc
                    if finalcost>limit:return None
                    ops.extend(base[1][oldidx:])
                    plan.update((k,x) for k,x in oldplan.items() if k[0]>=v)
                    if dc==0 and di==0:snaps.extend(base[3][v-1:])
                    else:snaps.extend((ss,mm,cc+dc,ii+di) for ss,mm,cc,ii in base[3][v-1:])
                    return (finalcost,ops,plan,snaps,params)
            snaps.append((tuple(stacks),tuple(mins),cost,len(ops)))
            src=loc[v];s=stacks[src];p=s.index(v)
            while len(s)>p+1:
                end=len(s);key=(v,s[-1]);old=oldplan.get(key)
                force=change is not None and key==change[0]
                cut=-1;bd=-1
                if old is not None:
                    bottom,dst=old
                    if dst!=src:
                        try:cut=s.index(bottom,p+1);bd=dst
                        except ValueError:pass
                kind=change[1] if force else -1
                if extra>0:
                    force=True;kind=2;extra-=1
                if force and kind==3:
                    extra=rng.randrange(1,4);kind=2
                if force and kind==1:
                    if cut<0:cut=end-1
                    if rng.random()<0.75:cut=max(p+1,min(end-1,cut+rng.choice((-2,-1,1,2))))
                    else:cut=rng.randrange(p+1,end)
                    if rng.random()<0.5:bd=-1
                if force and kind==2:cut=-1;bd=-1
                if cut<0:
                    tt=tol if not force else rng.choice((0,0,5,10,20,40,80,n))
                    cut=end-1;mx=s[cut]
                    if tt>=n:cut=p+1
                    else:
                        while cut>p+1 and s[cut-1]+tt>=mx:
                            cut-=1
                            if s[cut]>mx:mx=s[cut]
                if bd<0 or (force and kind==0):
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
                        opts=[x for x in opts if x[1]!=bd] or opts
                        r=rng.random();rank=0 if r<0.4 else 1 if r<0.7 else 2 if r<0.88 else rng.randrange(len(opts))
                        bd=opts[min(rank,len(opts)-1)][1]
                    else:bd=opts[0][1]
                block=s[cut:];cost+=len(block)+1
                if cost>limit:return None
                plan[key]=(block[0],bd);ops.append((block[0],bd+1))
                stacks[bd]=stacks[bd]+block;mins[bd]=min(mins[bd],min(block))
                for x in block:loc[x]=bd
                s=s[:cut];stacks[src]=s
            s=s[:-1];stacks[src]=s;mins[src]=min(s,default=empty);ops.append((v,0))
        return (cost,ops,plan,snaps,params)
    best=None;bestcost=100000
    for tol in (n,0,10,30,60):
        for mode in (0,1,2):
            for hw in (0.0,0.3,1.0):
                res=solve((tol,mode,hw),limit=bestcost)
                if res and res[0]<bestcost:best=res;bestcost=res[0]
    count=0
    while time.perf_counter()-start<0.30 and count<100:
        res=solve((rng.choice((0,0,5,10,20,40,80,n)),rng.randrange(3),rng.choice((0,0.1,0.3,0.6,1,2))),rng.choice((1,3,8,15)),limit=bestcost)
        if res and res[0]<bestcost:best=res;bestcost=res[0]
        count+=1
    cur=best;count=0
    while time.perf_counter()-start<1.74:
        if not cur[2]:break
        if count%180==0:cur=best
        key=rng.choice(list(cur[2]))
        r=rng.random();kind=0 if r<0.65 else 1 if r<0.89 else 2 if r<0.98 else 3
        elapsed=time.perf_counter()-start
        temp=max(0.2,4.0*(1-(elapsed-0.30)/1.44))
        allowance=-temp*math.log(max(1e-10,rng.random()))
        res=solve(cur[4],base=cur,change=(key,kind),limit=cur[0]+allowance)
        if res:
            cur=res
            if res[0]<bestcost:best=res;bestcost=res[0]
        count+=1
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in best[1])+'\n')
if __name__=='__main__':main()
