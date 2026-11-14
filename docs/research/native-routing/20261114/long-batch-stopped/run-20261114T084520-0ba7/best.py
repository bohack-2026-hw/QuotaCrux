import sys, time, random

def main():
    data = list(map(int, sys.stdin.buffer.read().split()))
    if not data:
        return
    n, m = data[:2]
    initial = [data[2+i*(n//m):2+(i+1)*(n//m)] for i in range(m)]
    start = time.perf_counter()
    rng = random.Random(260113)
    def solve(mode, noise, tolerance, lengthweight, limit):
        stacks = [x[:] for x in initial]
        loc = [0]*(n+1)
        for i,s in enumerate(stacks):
            for x in s:
                loc[x] = i
        mins = [min(s) if s else n+1 for s in stacks]
        out = []
        energy = 0
        for v in range(1,n+1):
            src = loc[v]
            s = stacks[src]
            p = s.index(v)
            while len(s)>p+1:
                end = len(s)
                if mode == 0:
                    cut = p+1
                else:
                    cut = end-1
                    low = s[cut]
                    while cut>p+1:
                        x = s[cut-1]
                        if x+tolerance < low:
                            break
                        low = min(low,x)
                        cut -= 1
                block = s[cut:]
                mx = max(block)
                if mode == 2:
                    top = s[-1]
                    possible = [j for j in range(m) if j!=src and mins[j]>top]
                    if possible:
                        target = min(possible, key=lambda j: mins[j]+lengthweight*len(stacks[j]))
                        threshold = mins[target]
                        cut = end-1
                        low = top
                        while cut>p+1 and s[cut-1]<threshold and s[cut-1]+tolerance>=low:
                            cut -= 1
                            low = min(low,s[cut])
                        block = s[cut:]
                        mx = max(block)
                opts = []
                for j in range(m):
                    if j==src:
                        continue
                    t = mins[j]
                    if t>mx:
                        key = t-mx
                    else:
                        key = n+1+(mx-t)*2
                    key += lengthweight*len(stacks[j])
                    if noise:
                        key += rng.uniform(-noise,noise)
                    opts.append((key,j))
                dest = min(opts)[1]
                out.append((block[0],dest+1))
                energy += len(block)+1
                if energy>=limit:
                    return None
                stacks[dest].extend(block)
                for x in block:
                    loc[x] = dest
                mins[dest] = min(mins[dest],min(block))
                del s[cut:]
            out.append((v,0))
            s.pop()
            mins[src] = min(s) if s else n+1
        if len(out)>5000:
            return None
        return energy,out
    # The original short-stack solution is retained as a guaranteed fallback.
    stacks = [s[:] for s in initial]
    fallback = []
    bestcost = 0
    for v in range(1,n+1):
        src = next(i for i,s in enumerate(stacks) if v in s)
        p = stacks[src].index(v)
        if p+1<len(stacks[src]):
            dest = min((j for j in range(m) if j!=src),key=lambda j:len(stacks[j]))
            block = stacks[src][p+1:]
            fallback.append((block[0],dest+1))
            bestcost += len(block)+1
            stacks[dest].extend(block)
            del stacks[src][p+1:]
        fallback.append((v,0))
        stacks[src].pop()
    best = fallback
    configurations = [(0,0,0,0),(1,0,0,0),(2,0,0,0),(1,0,10,0),(1,0,30,0),(2,0,20,0),(0,0,0,0.5),(1,0,0,0.5),(2,0,0,0.5)]
    iteration = 0
    while time.perf_counter()-start < 1.55:
        if iteration<len(configurations):
            args = configurations[iteration]
        else:
            args = (rng.choice((0,1,1,2,2)), rng.choice((0,4,10,20,40)), rng.choice((0,0,0,5,10,20,40,80)), rng.choice((0,0,0.1,0.3,0.8,1.5)))
        result = solve(*args,bestcost)
        if result is not None and result[0]<bestcost:
            bestcost,best = result
        iteration += 1
    sys.stdout.write('\n'.join(str(v)+' '+str(d) for v,d in best)+'\n')

if __name__ == '__main__':
    main()
