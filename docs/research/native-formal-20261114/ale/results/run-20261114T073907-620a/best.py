import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    idx = 0
    n, m = data[idx], data[idx+1]
    idx += 2
    h = n // m
    stacks = []
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    ops = []
    
    for value in range(1, n + 1):
        # Find which stack contains 'value'
        src = -1
        pos = -1
        for si in range(m):
            if value in stacks[si]:
                src = si
                pos = stacks[si].index(value)
                break
        
        if pos + 1 < len(stacks[src]):
            above = stacks[src][pos+1:]
            max_above = max(above)
            
            # Find valid destination stacks: those where all boxes have number > max_above
            # Empty stacks are always valid
            candidates = []
            for di in range(m):
                if di == src:
                    continue
                if len(stacks[di]) == 0:
                    candidates.append((di, 0))  # empty stack, priority 0
                else:
                    min_in_dest = min(stacks[di])
                    if min_in_dest > max_above:
                        # Valid! Prefer shorter stacks, then larger top values
                        priority = len(stacks[di]) * 1000 - (stacks[di][-1] if stacks[di] else 0)
                        candidates.append((di, priority))
            
            if candidates:
                # Choose the best candidate (lowest priority value)
                candidates.sort(key=lambda x: x[1])
                best_dest = candidates[0][0]
            else:
                # No valid candidate; choose the shortest non-src stack as fallback
                best_dest = min((j for j in range(m) if j != src), key=lambda j: len(stacks[j]))
            
            ops.append((above[0], best_dest + 1))
            stacks[best_dest].extend(above)
            del stacks[src][pos+1:]
        
        ops.append((value, 0))
        stacks[src].pop()
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()