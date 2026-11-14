import sys

def solve():
    it = iter(map(int, sys.stdin.buffer.read().split()))
    n, m = next(it), next(it)
    stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
    
    # Build position map
    pos_map = {}
    for i, stack in enumerate(stacks):
        for j, val in enumerate(stack):
            pos_map[val] = (i, j)
    
    ops = []
    total_energy = 0
    
    for value in range(1, n + 1):
        src, pos = pos_map[value]
        if pos + 1 < len(stacks[src]):
            above = stacks[src][pos + 1:]
            k = len(above)
            
            # Find best destination: prefer shortest stack, then stack with largest min value
            # This minimizes future energy cost
            best_dest = -1
            best_key = None
            for j in range(m):
                if j == src:
                    continue
                # Key: (length, -min_value) to prefer shorter and larger values
                if not stacks[j]:
                    key = (0, float('inf'))
                else:
                    key = (len(stacks[j]), -min(stacks[j]))
                if best_key is None or key < best_key:
                    best_key = key
                    best_dest = j
            
            dest = best_dest
            ops.append((above[0], dest + 1))
            total_energy += k + 1
            
            # Update stacks
            stacks[dest].extend(above)
            del stacks[src][pos + 1:]
            
            # Update pos_map for moved boxes
            base_idx = len(stacks[dest]) - k
            for idx, box in enumerate(above):
                pos_map[box] = (dest, base_idx + idx)
        
        ops.append((value, 0))
        del stacks[src][pos]
        
        # Update pos_map for remaining boxes in src stack
        for idx in range(pos, len(stacks[src])):
            pos_map[stacks[src][idx]] = (src, idx)
    
    out = []
    for v, i in ops:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
