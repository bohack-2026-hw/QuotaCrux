import sys,time

def main():
    data=list(map(int,sys.stdin.buffer.read().split()))
    if not data:return
    n,m=data[:2]
    initial=[data[2+i*(n//m):2+(i+1)*(n//m)] for i in range(m)]
    start=time.perf_counter()
    deadline=start+1.65
    def solve(lam,gap,mode):
        stacks=[s[:] for s in initial]
        where=[0]*(n+1)
        for i,s in enumerate(stacks):
            for x in s:where[x]=i
        ops=[];energy=0
        for v in range(1,n+1):
            src=where[v];s=stacks[src];p=s.index(v)
            h=len(s)
            if p+1<h:
                mins=[min(t) if t else n+1 for t in stacks]
                def dest_for(x):
                    good=[j for j in range(m) if j!=src and mins[j]>x]
                    if good:
                        return min(good,key=lambda j:(mins[j],len(stacks[j])))
                    return max((j for j in range(m) if j!=src),key=lambda j:(mins[j],-len(stacks[j])))
                lo=p+1;k=h-lo
                if lam==0 or k==1:
                    parts=[(lo,h)]
                else:
                    a=s[lo:]
                    dp=[0.0]+[1e100]*k
                    prev=[0]*(k+1)
                    for l in range(k):
                        d=dest_for(a[l]);mn=mins[d]
                        bad=0.0;base=dp[l]+1.0
                        for r in range(l,k):
                            x=a[r]
                            if x>mn:
                                bad+=1.0+gap*(x-mn)/n
                            else:mn=x
                            z=base+lam*bad
                            if z<dp[r+1]:dp[r+1]=z;prev[r+1]=l
                    parts=[];r=k
                    while r:
                        l=prev[r];parts.append((lo+l,lo+r));r=l
                    parts.reverse()
                for l,r in reversed(parts):
                    d=dest_for(s[l])
                    block=s[l:]
                    ops.append((block[0],d+1));energy+=len(block)+1
                    stacks[d].extend(block)
                    for x in block:where[x]=d
                    mins[d]=min(mins[d],min(block))
                    del s[l:]
            ops.append((v,0));s.pop()
            if len(ops)>4800:return 10**9,[]
        return energy,ops
    best,answer=solve(0,0,0)
    params=[(1.0,0),(1.3,0),(1.7,0),(2.3,0),(0.8,1.5),(1.1,2),(1.5,2),(2.0,2),(0.6,4),(1.0,4),(1.5,4),(2.0,4),(3.0,1),(4.0,1),(0.9,0.4),(1.2,0.5),(1.7,0.7),(2.5,3)]
    for lam,gap in params:
        if time.perf_counter()>deadline:break
        energy,ops=solve(lam,gap,0)
        if energy<best:best,answer=energy,ops
    sys.stdout.write('\n'.join(str(v)+' '+str(i) for v,i in answer))

if __name__=='__main__':main()
