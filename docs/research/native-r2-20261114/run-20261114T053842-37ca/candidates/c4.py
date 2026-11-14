import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    idx = 2
    stacks = []
    for i in range(m):
        stack = data[idx:idx + n // m]
        stacks.append(stack)
        idx += n // m
    
    # Build position map
    pos = {}
    for i, stack in enumerate(stacks):
        for j, v in enumerate(stack):
            pos[v] = (i, j)
    
    ops = []
    
    for value in range(1, n + 1):
        src_i, src_j = pos[value]
        if src_j < len(stacks[src_i]) - 1:
            # Need to move boxes above value
            above = stacks[src_i][src_j + 1:]
            first_above = above[0]
            
            # Choose destination: prefer empty stacks, then shortest
            best_dest = None
            min_cost = float('inf')
            for j in range(m):
                if j == src_i:
                    continue
                # Cost heuristic: prefer shorter stacks
                cost = len(stacks[j])
                if cost < min_cost:
                    min_cost = cost
                    best_dest = j
            
            ops.append((first_above, best_dest + 1))
            
            # Update state
            moved = stacks[src_i][src_j + 1:]
            del stacks[src_i][src_j + 1:]
            stacks[best_dest].extend(moved)
            
            # Update positions
            for k, v in enumerate(moved):
                pos[v] = (best_dest, len(stacks[best_dest]) - len(moved) + k)
        
        # Carry out value
        ops.append((value, 0))
        
        # Remove from stack
        si, sj = pos[value]
        assert stacks[si][-1] == value, f"Expected {value} at top of stack {si}, got {stacks[si]}"
        stacks[si].pop()
        del pos[value]
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    print('\n'.join(out))

solve()