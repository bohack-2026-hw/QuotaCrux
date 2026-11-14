import sys, time, random, math

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    if not data:
        return
    n, m = data[:2]
    z = n // m
    initial = [data[2+i*z:2+(i+1)*z] for i in range(m)]
    start = time.perf_counter()
    deadline = start + 1.62
    inf = n + 1
    rng = random.Random(1783127 + sum((i+1)*x for i,x in enumerate(data[2:])))
    stacks = [a[:] for a in initial]
    best = []
    best_cost = 0
    for v in range(1,n+1):
        s = next(i for i,a in enumerate(stacks) if v in a)
        a = stacks[s]
        p = a.index(v)
        if p+1 < len(a):
            d = min((j for j in range(m) if j != s), key=lambda j: len(stacks[j]))
            block = a[p+1:]
            best.append((block[0],d+1))
            best_cost += len(block)+1
            stacks[d].extend(block)
            del a[p+1:]
        best.append((v,0))
        a.pop()

    def solve(params, plan, override, bound):
        mode, fit, height, noise, fn = params
        stacks = [a[:] for a in initial]
        mins = [min(a) if a else inf for a in stacks]
        loc = [0]*(n+1)
        for j,a in enumerate(stacks):
            for x in a:
                loc[x] = j
        ans = []
        trace = []
        energy = 0
        for v in range(1,n+1):
            if (v & 31) == 0 and time.perf_counter() >= deadline:
                return None
            s = loc[v]
            a = stacks[s]
            p = a.index(v)
            while len(a)>p+1:
                h = len(a)
                key = v*(n+1)+a[-1]
                choice = override[1] if override is not None and key == override[0] else plan.get(key)
                cut = -1
                d = -1
                if choice is not None and choice[1] != s:
                    b, dd = choice
                    try:
                        cc = a.index(b,p+1)
                        cut, d = cc, dd
                    except ValueError:
                        pass
                if cut < 0:
                    if mode == 2:
                        cut = p+1
                        threshold = max(a[cut:])
                    else:
                        cut = h-1
                        while cut>p+1 and a[cut-1]>a[cut]:
                            cut -= 1
                        if mode == 1:
                            cap = max(mins[j] for j in range(m) if j != s)
                            if a[-1] < cap:
                                while cut < h-1 and a[cut] > cap:
                                    cut += 1
                        threshold = a[cut]
                    safe_best = 1e100
                    forced_best = 1e100
                    safe_d = -1
                    forced_d = -1
                    for j in range(m):
                        if j == s:
                            continue
                        if mins[j]>threshold:
                            score = fit*(mins[j]-threshold)+height*len(stacks[j])
                            if noise:
                                score += rng.random()*noise
                            if score<safe_best:
                                safe_best, safe_d = score,j
                        else:
                            score = -mins[j]+height*0.12*len(stacks[j])
                            if fn:
                                score += rng.random()*fn
                            if score<forced_best:
                                forced_best,forced_d = score,j
                    d = safe_d if safe_d>=0 else forced_d
                block = a[cut:]
                trace.append((key,block[0],d,s,tuple(a[p+1:]),tuple(mins)))
                energy += len(block)+1
                if energy >= bound:
                    return None
                ans.append((block[0],d+1))
                stacks[d].extend(block)
                mins[d] = min(mins[d],min(block))
                for x in block:
                    loc[x] = d
                del a[cut:]
            a.pop()
            mins[s] = min(a) if a else inf
            ans.append((v,0))
        return energy,ans,trace

    best_trace = None
    best_params = None
    empty = {}
    settings = [(mo,fit,hei,0,0) for mo in (0,1,2) for fit,hei in ((1,0),(1,0.5),(1,2),(0,1),(-0.25,0.5))]
    for params in settings:
        result = solve(params,empty,None,best_cost)
        if result is not None:
            best_cost,best,best_trace = result
            best_params = params[:3]+(0,0)
    while time.perf_counter() < start+0.34:
        params = (rng.choices((0,1,2),(5,5,1))[0],rng.choice((0.3,0.6,1.0,1.5)),rng.choice((0.0,0.2,0.7,1.5,3.0)),rng.choice((0.0,2.0,5.0,10.0,20.0,40.0)),rng.choice((0.0,2.0,5.0,10.0,20.0)))
        result = solve(params,empty,None,best_cost)
        if result is not None:
            best_cost,best,best_trace = result
            best_params = params[:3]+(0,0)
    if best_trace:
        current_cost = best_cost
        current_trace = best_trace
        params = best_params
        plan = {t[0]:(t[1],t[2]) for t in current_trace}
        iterations = 0
        while time.perf_counter() < deadline:
            iterations += 1
            if iterations % 140 == 0:
                current_cost,current_trace = best_cost,best_trace
                plan = {t[0]:(t[1],t[2]) for t in current_trace}
            t = rng.choice(current_trace)
            key,b,d,s,blocked,mn = t
            idx = blocked.index(b)
            if rng.random()<0.29:
                r = rng.random()
                if r<0.35:
                    idx = 0
                elif r<0.65:
                    idx = len(blocked)-1
                else:
                    idx = rng.randrange(len(blocked))
                b = blocked[idx]
            threshold = max(blocked[idx:])
            dests = [j for j in range(m) if j!=s and (j!=d or b!=t[1])]
            if not dests:
                continue
            if rng.random()<0.72:
                dests.sort(key=lambda j: (mn[j]-threshold if mn[j]>threshold else 500-mn[j]))
                d = rng.choice(dests[:rng.choice((1,2,3,5))])
            else:
                d = rng.choice(dests)
            elapsed = (time.perf_counter()-start)/1.62
            temp = 4.5*(1-elapsed)+0.25
            result = solve(params,plan,(key,(b,d)),current_cost+max(12,9*temp))
            if result is None:
                continue
            cost,ans,trace = result
            if cost<best_cost:
                best_cost,best,best_trace = cost,ans,trace
            delta = cost-current_cost
            if delta<=0 or rng.random()<math.exp(-delta/temp):
                current_cost,current_trace = cost,trace
                plan = {t[0]:(t[1],t[2]) for t in trace}
    sys.stdout.write('\n'.join(str(v)+' '+str(d) for v,d in best)+'\n')

if __name__ == '__main__':
    main()
