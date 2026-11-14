import sys

def solve():
    it = iter(map(int, sys.stdin.buffer.read().split()))
    n, m = next(it), next(it)
    stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
    
    # Build position map for faster lookup
    pos_map = {}
    for i, stack in enumerate(stacks):
        for j, val in enumerate(stack):
            pos_map[val] = (i, j)
    
    ops = []
    total_energy = 0
    
    for value in range(1, n + 1):
        src, pos = pos_map[value]
        if pos + 1 < len(stacks[src]):
            # Find best destination: minimize energy impact
            # We want to move boxes above value to a stack where they won't cause issues later
            # Strategy: move to the shortest stack that doesn't contain smaller unprocessed boxes
            candidates = []
            for j in range(m):
                if j == src:
                    continue
                # Check if moving here would be beneficial
                # Prefer shorter stacks and stacks without small numbers
                min_val_in_dest = min(stacks[j]) if stacks[j] else float('inf')
                candidates.append((len(stacks[j]), min_val_in_dest, j))
            
            candidates.sort()
            dest = candidates[0][2]
            
            above = stacks[src][pos + 1:]
            k = len(above)
            ops.append((above[0], dest + 1))
            total_energy += k + 1
            
            # Update stacks
            stacks[dest].extend(above)
            del stacks[src][pos + 1:]
            
            # Update pos_map for moved boxes
            for idx, box in enumerate(above):
                pos_map[box] = (dest, len(stacks[dest]) - len(above) + idx)
        
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