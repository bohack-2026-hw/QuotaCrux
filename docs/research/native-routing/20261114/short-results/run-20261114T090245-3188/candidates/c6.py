import sys, time, random, math

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    if not data:
        return
    n, m = data[:2]
    z = n // m
    initial = [data[2+i*z:2+(i+1)*z] for i in range(m)]
    start = time.perf_counter()
    duration = 1.67
    deadline = start + duration
    inf = n + 1
    rng = random.Random(1783127 + sum((i+1)*x for i,x in enumerate(data[2:])))
    initloc = [0]*(n+1)
    for j,a in enumerate(initial):
        for x in a:
            initloc[x] = j
    initmins = [min(a) if a else inf for a in initial]
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

    def solve(params, plan, override, bound, prefix=None):
        mode, fit, height, noise, fn = params
        if prefix is None:
            stacks = [a[:] for a in initial]
            mins = initmins[:]
            loc = initloc[:]
            ans = []
            trace = []
            energy = 0
            first = 1
        else:
            state, oldans, oldtrace, ti = prefix
            ss, mm, ll, energy, ai, first = state
            stacks = [a[:] for a in ss]
            mins = mm[:]
            loc = ll[:]
            ans = oldans[:ai]
            trace = oldtrace[:ti]
        for v in range(first,n+1):
            if (v & 15) == 0 and time.perf_counter() >= deadline:
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
                trace.append((key,block[0],d))
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

    def make_cache(ans, oldcache=None, ti=0):
        if oldcache is None:
            stacks = [a[:] for a in initial]
            mins = initmins[:]
            loc = initloc[:]
            energy = 0
            first = 1
            ai = 0
            cache = []
        else:
            ss,mm,ll,energy,ai,first = oldcache[ti]
            stacks = [a[:] for a in ss]
            mins = mm[:]
            loc = ll[:]
            cache = oldcache[:ti]
        for k in range(ai,len(ans)):
            b,dd = ans[k]
            s = loc[b]
            a = stacks[s]
            if dd == 0:
                a.pop()
                mins[s] = min(a) if a else inf
                first = b+1
            else:
                cache.append(([q[:] for q in stacks],mins[:],loc[:],energy,k,first))
                d = dd-1
                p = a.index(b)
                block = a[p:]
                energy += len(block)+1
                del a[p:]
                stacks[d].extend(block)
                mins[d] = min(mins[d],min(block))
                mins[s] = min(a) if a else inf
                for x in block:
                    loc[x] = d
        return cache

    best_trace = None
    best_params = None
    empty = {}
    settings = [(mo,fit,hei,0,0) for mo in (0,1,2) for fit,hei in ((1,0),(1,0.5),(1,2),(0,1),(-0.25,0.5))]
    for params in settings:
        result = solve(params,empty,None,best_cost)
        if result is not None:
            best_cost,best,best_trace = result
            best_params = params[:3]+(0,0)
    while time.perf_counter() < start+0.28:
        params = (rng.choices((0,1,2),(5,5,1))[0],rng.choice((0.3,0.6,1.0,1.5)),rng.choice((0.0,0.2,0.7,1.5,3.0)),rng.choice((0.0,2.0,5.0,10.0,20.0,40.0)),rng.choice((0.0,2.0,5.0,10.0,20.0)))
        result = solve(params,empty,None,best_cost)
        if result is not None:
            best_cost,best,best_trace = result
            best_params = params[:3]+(0,0)
    if best_trace:
        current_cost = best_cost
        current_trace = best_trace
        current_ans = best
        params = best_params
        plan = {t[0]:(t[1],t[2]) for t in current_trace}
        cache = make_cache(current_ans)
        iterations = 0
        while time.perf_counter() < deadline:
            iterations += 1
            if iterations % 240 == 0:
                current_cost,current_trace,current_ans = best_cost,best_trace,best
                plan = {t[0]:(t[1],t[2]) for t in current_trace}
                cache = make_cache(current_ans)
            ti = rng.randrange(len(current_trace))
            key,b,d = current_trace[ti]
            state = cache[ti]
            ss,mn,ll,ec,ai,v = state
            s = ll[v]
            a = ss[s]
            p = a.index(v)
            blocked = a[p+1:]
            idx = blocked.index(b)
            if rng.random()<0.32:
                r = rng.random()
                if r<0.30:
                    idx = 0
                elif r<0.55:
                    idx = len(blocked)-1
                elif r<0.80:
                    cuts = [j for j in range(len(blocked)-1) if blocked[j]<blocked[j+1]]
                    idx = rng.choice(cuts) if cuts else rng.randrange(len(blocked))
                else:
                    idx = rng.randrange(len(blocked))
                b = blocked[idx]
            threshold = max(blocked[idx:])
            dests = [j for j in range(m) if j!=s and (j!=d or b!=current_trace[ti][1])]
            if not dests:
                continue
            if rng.random()<0.75:
                dests.sort(key=lambda j: (mn[j]-threshold if mn[j]>threshold else 500-mn[j]))
                d = rng.choice(dests[:rng.choice((1,2,3,5))])
            else:
                d = rng.choice(dests)
            elapsed = (time.perf_counter()-start)/duration
            temp = 4.0*(1-elapsed)+0.20
            result = solve(params,plan,(key,(b,d)),current_cost+max(12,9*temp),(state,current_ans,current_trace,ti))
            if result is None:
                continue
            cost,ans,trace = result
            if cost<best_cost:
                best_cost,best,best_trace = cost,ans,trace
            delta = cost-current_cost
            if delta<=0 or rng.random()<math.exp(-delta/temp):
                cache = make_cache(ans,cache,ti)
                current_cost,current_ans,current_trace = cost,ans,trace
                plan = {t[0]:(t[1],t[2]) for t in trace}
    sys.stdout.write('\n'.join(str(v)+' '+str(d) for v,d in best)+'\n')

if __name__ == '__main__':
    main()
