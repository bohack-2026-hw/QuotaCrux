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
            
            # Find best destination using a more sophisticated heuristic
            # We want to minimize future energy cost. Consider:
            # 1. Stack length (shorter is better)
            # 2. The minimum value in the stack (larger is better, as smaller values will be processed sooner)
            # 3. How many boxes in the destination stack are larger than the current value (fewer is better)
            best_dest = -1
            best_score = float('inf')
            
            for j in range(m):
                if j == src:
                    continue
                
                # Calculate a score for this destination
                dest_stack = stacks[j]
                if not dest_stack:
                    score = 0
                else:
                    # Primary: stack length
                    score = len(dest_stack)
                    # Secondary: prefer stacks with larger minimum values
                    min_val = min(dest_stack)
                    score += (n - min_val) / n * 0.5
                    # Tertiary: count how many boxes are larger than current value
                    larger_count = sum(1 for x in dest_stack if x > value)
                    score += larger_count * 0.1
                
                if score < best_score:
                    best_score = score
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
