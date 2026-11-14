import sys

def solve():
    data = sys.stdin.buffer.read().split()
    n, m = int(data[0]), int(data[1])
    stacks = []
    idx = 2
    for i in range(m):
        stack = [int(data[idx + j]) for j in range(n // m)]
        stacks.append(stack)
        idx += n // m
    
    ops = []
    total_ops = 0
    
    for value in range(1, n + 1):
        # Find which stack contains 'value'
        src = -1
        pos = -1
        for i, stack in enumerate(stacks):
            if value in stack:
                src = i
                pos = stack.index(value)
                break
        
        if pos + 1 < len(stacks[src]):
            # Need to move boxes above 'value'
            above = stacks[src][pos + 1:]
            # Choose destination stack that minimizes future cost
            # Heuristic: pick the shortest stack (or one that doesn't contain small values)
            dest = min((j for j in range(m) if j != src), key=lambda j: len(stacks[j]))
            ops.append((above[0], dest + 1))
            total_ops += 1
            stacks[dest].extend(above)
            del stacks[src][pos + 1:]
        
        ops.append((value, 0))
        total_ops += 1
        stacks[src].pop()
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()