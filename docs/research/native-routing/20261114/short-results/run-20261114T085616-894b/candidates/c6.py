import sys,time,random
from bisect import bisect_right

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    if not data:return
    n,m=data[:2];w=n//m
    initial=[data[2+i*w:2+(i+1)*w] for i in range(m)]
    deadline=time.perf_counter()+1.76
    rng=random.Random(91723)
    def solve(params,sv=1,snap=None):
        if snap is None:
            stacks=[s[:] for s in initial];energy=0
        else:
            stacks=[s[:] for s in snap[0]];energy=snap[1]
        where=[0]*(n+1);ops=[]
        for i,s in enumerate(stacks):
            for x in s:where[x]=i
        for v in range(sv,n+1):
            src=where[v];s=stacks[src];p=s.index(v);h=len(s)
            if p+1<h:
                lam,gap,rank=params[v]
                mins=[min(t) if t else n+1 for t in stacks]
                order=sorted((j for j in range(m) if j!=src),key=lambda j:(mins[j],len(stacks[j])))
                keys=[mins[j] for j in order]
                fallback=sorted(order,key=lambda j:(-mins[j],len(stacks[j])))[min(rank,m-2)]
                lo=p+1;k=h-lo
                if lam==0 or k==1:parts=[lo]
                else:
                    a=s[lo:];dp=[0.0]+[1e100]*k;prev=[0]*(k+1);gn=gap/n
                    for l in range(k):
                        base=dp[l]+1.0
                        if base>dp[k]:continue
                        q=bisect_right(keys,a[l])
                        d=order[min(q+rank,m-2)] if q<m-1 else fallback
                        mn=mins[d];bad=0.0
                        for r in range(l,k):
                            x=a[r]
                            if x>mn:bad+=1.0+gn*(x-mn)
                            else:mn=x
                            z=base+lam*bad
                            if z>dp[k]:break
                            if z<dp[r+1]:dp[r+1]=z;prev[r+1]=l
                    parts=[];r=k
                    while r:
                        l=prev[r];parts.append(lo+l);r=l
                for l in parts:
                    x=s[l]
                    order=sorted((j for j in range(m) if j!=src),key=lambda j:(mins[j],len(stacks[j])))
                    keys=[mins[j] for j in order];q=bisect_right(keys,x)
                    if q<m-1:d=order[min(q+rank,m-2)]
                    else:d=sorted(order,key=lambda j:(-mins[j],len(stacks[j])))[min(rank,m-2)]
                    block=s[l:];ops.append((x,d+1));energy+=len(block)+1
                    stacks[d].extend(block)
                    for x in block:where[x]=d
                    mins[d]=min(mins[d],min(block));del s[l:]
            ops.append((v,0));s.pop()
        return energy,ops
    plist=[(0,0),(1.0,0),(1.3,0),(1.7,0),(2.3,0),(0.8,1.5),(1.1,2),(1.5,2),(2.0,2),(0.6,4),(1.0,4),(1.5,4),(2.0,4),(3.0,1),(4.0,1),(0.9,0.4),(1.2,0.5),(1.7,0.7),(2.5,3)]
    best=10**9;answer=[];params=None
    for lam,gap in plist:
        if time.perf_counter()>deadline-0.12 and params is not None:break
        pp=[(lam,gap,0)]*(n+1)
        en,ops=solve(pp)
        if en<best:best,answer,params=en,ops,pp
    def history(ops):
        stacks=[s[:] for s in initial];where=[0]*(n+1)
        for i,s in enumerate(stacks):
            for x in s:where[x]=i
        hist=[None]*(n+2);active=[];e=0;v=1
        hist[1]=([s[:] for s in stacks],0,0)
        if stacks[where[v]][-1]!=v:active.append(v)
        for oi,(x,d) in enumerate(ops):
            src=where[x];s=stacks[src]
            if d:
                p=s.index(x);block=s[p:];e+=len(block)+1
                stacks[d-1].extend(block)
                for y in block:where[y]=d-1
                del s[p:]
            else:
                s.pop();v=x+1
                if v<=n:
                    hist[v]=([t[:] for t in stacks],e,oi+1)
                    if stacks[where[v]][-1]!=v:active.append(v)
        return hist,active
    hist,active=history(answer)
    current=best;cur_ops=answer;cur_params=params[:]
    while active and time.perf_counter()<deadline:
        v=rng.choice(active);old=cur_params[v];r=rng.random()
        if r<0.68:
            new=(rng.choice((0.0,0.45,0.7,0.9,1.1,1.4,1.8,2.4,3.2,4.5,7.0)),rng.choice((0.0,0.5,1.5,3.0,6.0)),0 if rng.random()<0.9 else 1)
        elif r<0.9:new=(old[0]*rng.choice((0.65,0.85,1.2,1.5)),old[1],old[2])
        else:new=(old[0],old[1],rng.choice((0,1,2)))
        if new==old:continue
        cur_params[v]=new
        en,suffix=solve(cur_params,v,hist[v])
        if en<=current and len(suffix)+hist[v][2]<=5000:
            current=en;cur_ops=cur_ops[:hist[v][2]]+suffix
            hist,active=history(cur_ops)
            if en<best:best=en;answer=cur_ops
        else:cur_params[v]=old
    sys.stdout.write('\n'.join(str(v)+' '+str(d) for v,d in answer))

if __name__=='__main__':main()
