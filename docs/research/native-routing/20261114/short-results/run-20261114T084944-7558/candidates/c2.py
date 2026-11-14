import sys, time, random

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    if not data:
        return
    n, m = data[:2]
    initial = [data[2+i*(n//m):2+(i+1)*(n//m)] for i in range(m)]
    rng = random.Random(17731 + sum((i+1)*v for i,v in enumerate(data[2:])))
    start = time.perf_counter()
    best_cost = 10**9
    best_ops = []
    def solve(tol, mode, height_weight, noise):
        nonlocal best_cost, best_ops
        stacks = [s[:] for s in initial]
        loc = [0]*(n+1)
        mins = [min(s, default=n+1) for s in stacks]
        for i,s in enumerate(stacks):
            for x in s:
                loc[x] = i
        cost = 0
        ops = []
        for v in range(1,n+1):
            src = loc[v]
            s = stacks[src]
            p = s.index(v)
            while len(s)>p+1:
                end = len(s)
                cut = end-1
                mx = s[cut]
                if tol >= n:
                    cut = p+1
                    mx = max(s[cut:])
                else:
                    while cut>p+1 and s[cut-1]+tol>=mx:
                        cut -= 1
                        if s[cut]>mx:
                            mx=s[cut]
                block=s[cut:]
                mn=min(block)
                if mode==0:
                    pivot=mx
                elif mode==1:
                    pivot=mn
                else:
                    pivot=(mx+mn)*0.5
                bd=-1
                bs=1e30
                for d in range(m):
                    if d==src:
                        continue
                    md=mins[d]
                    if md>=pivot:
                        z=(md-pivot)*0.08
                    else:
                        z=100+(pivot-md)
                    z += height_weight*len(stacks[d])
                    if noise:
                        z += rng.random()*noise
                    if z<bs:
                        bs=z
                        bd=d
                ops.append((block[0],bd+1))
                cost+=len(block)+1
                if cost>=best_cost:
                    return
                stacks[bd].extend(block)
                mins[bd]=min(mins[bd],mn)
                for x in block:
                    loc[x]=bd
                del s[cut:]
            ops.append((v,0))
            s.pop()
            mins[src]=min(s,default=n+1)
        if cost<best_cost:
            best_cost=cost
            best_ops=ops
    for tol in (n,0,10,30,60):
        for mode in (0,1,2):
            for hw in (0.0,0.3,1.0):
                solve(tol,mode,hw,0.0)
    count=0
    while time.perf_counter()-start<1.55 and count<350:
        solve(rng.choice((0,0,5,10,20,40,80,n)),rng.randrange(3),rng.choice((0,0.1,0.3,0.6,1,2)),rng.choice((1,3,8,15)))
        count+=1
    sys.stdout.write('\n'.join(f'{v} {d}' for v,d in best_ops)+'\n')

if __name__=='__main__':
    main()
