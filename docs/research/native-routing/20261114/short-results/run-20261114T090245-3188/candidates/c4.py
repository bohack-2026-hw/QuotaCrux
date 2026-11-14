import sys, time, random

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    if not data:
        return
    n, m = data[:2]
    z = n // m
    initial = [data[2+i*z:2+(i+1)*z] for i in range(m)]
    start = time.perf_counter()
    deadline = start + 1.55
    inf = n + 1
    rng = random.Random(1783127 + sum((i+1)*x for i, x in enumerate(data[2:])))
    # A cheap, universally feasible incumbent.
    stacks = [a[:] for a in initial]
    best = []
    best_cost = 0
    for v in range(1, n+1):
        s = next(i for i,a in enumerate(stacks) if v in a)
        a = stacks[s]
        p = a.index(v)
        if p+1 < len(a):
            d = min((i for i in range(m) if i != s), key=lambda i: len(stacks[i]))
            block = a[p+1:]
            best.append((block[0], d+1))
            best_cost += len(block)+1
            stacks[d].extend(block)
            del a[p+1:]
        best.append((v, 0))
        a.pop()

    def solve(mode, fit, height, noise, forced_noise):
        nonlocal best_cost, best
        stacks = [a[:] for a in initial]
        mins = [min(a) if a else inf for a in stacks]
        loc = [0]*(n+1)
        for i,a in enumerate(stacks):
            for x in a:
                loc[x] = i
        ans = []
        energy = 0
        for v in range(1,n+1):
            if (v & 31) == 0 and time.perf_counter() >= deadline:
                return
            s = loc[v]
            a = stacks[s]
            p = a.index(v)
            while len(a) > p+1:
                h = len(a)
                if mode == 2:
                    cut = p+1
                    threshold = max(a[cut:])
                else:
                    cut = h-1
                    while cut > p+1 and a[cut-1] > a[cut]:
                        cut -= 1
                    if mode == 1:
                        cap = max(mins[d] for d in range(m) if d != s)
                        if a[-1] < cap:
                            while cut < h-1 and a[cut] > cap:
                                cut += 1
                    threshold = a[cut]
                safe = [d for d in range(m) if d != s and mins[d] > threshold]
                if safe:
                    d = min(safe, key=lambda j: fit*(mins[j]-threshold) + height*len(stacks[j]) + (rng.random()*noise if noise else 0.0))
                else:
                    d = min((j for j in range(m) if j != s), key=lambda j: -mins[j] + height*0.12*len(stacks[j]) + (rng.random()*forced_noise if forced_noise else 0.0))
                block = a[cut:]
                energy += len(block)+1
                if energy >= best_cost or len(ans) >= 4790:
                    return
                ans.append((block[0], d+1))
                stacks[d].extend(block)
                mins[d] = min(mins[d], min(block))
                for x in block:
                    loc[x] = d
                del a[cut:]
            a.pop()
            mins[s] = min(a) if a else inf
            ans.append((v,0))
        if energy < best_cost and len(ans) <= 5000:
            best_cost = energy
            best = ans

    for mode in (0, 1, 2):
        for fit, height in ((1,0), (1,0.5), (1,2), (0,1), (-0.25,0.5)):
            if time.perf_counter() >= deadline:
                break
            solve(mode,fit,height,0,0)
    while time.perf_counter() < deadline:
        mode = rng.choices((0,1,2), (5,5,1))[0]
        fit = rng.choice((0.3,0.6,1.0,1.5))
        height = rng.choice((0.0,0.2,0.7,1.5,3.0))
        noise = rng.choice((0.0,2.0,5.0,10.0,20.0,40.0))
        forced_noise = rng.choice((0.0,2.0,5.0,10.0,20.0))
        solve(mode,fit,height,noise,forced_noise)
    sys.stdout.write('\n'.join(str(v)+' '+str(d) for v,d in best)+'\n')

if __name__ == '__main__':
    main()
