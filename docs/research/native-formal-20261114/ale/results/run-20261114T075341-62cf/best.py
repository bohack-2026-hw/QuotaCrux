import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    h = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+h])
        idx += h
    
    # Build position map: box value -> (stack_idx, position_in_stack)
    pos = {}
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    operations = []
    energy = 0
    
    for value in range(1, n + 1):
        src, pos_in_src = pos[value]
        if pos_in_src < len(stacks[src]) - 1:
            # Need to move boxes above value
            above = stacks[src][pos_in_src + 1:]
            k = len(above)
            
            # Choose destination stack optimally
            # Strategy: try all possible destinations and pick the one that
            # minimizes future cost. Use a heuristic: prefer moving to a stack
            # where the minimum box in 'above' can be freed quickly.
            
            best_dest = -1
            best_score = float('inf')
            
            for dest in range(m):
                if dest == src:
                    continue
                # Heuristic score: we want to minimize total energy.
                # Moving 'above' to dest costs k+1.
                # After this, the min of 'above' will be at some position in dest.
                # A good heuristic: prefer dest where the top of dest has larger values
                # (so 'above' sits on top and its min is accessible sooner),
                # or where dest is empty.
                
                # Actually, let's think differently. The key insight from similar problems:
                # When we need to move a group of boxes, we should move them to a stack
                # such that the smallest box in the moved group ends up as close to the
                # top as possible relative to other pending boxes.
                
                # Simple effective heuristic: move to the stack with the fewest boxes
                # that don't contain any box smaller than min(above).
                # Even simpler: just try each dest and simulate briefly.
                
                # Let's use: prefer dest where after adding 'above', the number of
                # boxes below min(above) in that stack is minimized.
                min_above = min(above)
                # Count how many boxes in dest are smaller than min_above
                # (these would block min_above from being accessed)
                blockers = sum(1 for x in stacks[dest] if x < min_above)
                # Also consider current length of dest
                score = blockers * 10 + len(stacks[dest])
                
                if score < best_score:
                    best_score = score
                    best_dest = dest
            
            # Execute move
            operations.append((above[0], best_dest + 1))
            energy += k + 1
            
            # Update stacks
            stacks[best_dest].extend(above)
            del stacks[src][pos_in_src + 1:]
            
            # Update positions for moved boxes
            for j, v in enumerate(above):
                pos[v] = (best_dest, len(stacks[best_dest]) - len(above) + j)
        else:
            pass  # value is already at top
        
        # Carry out value
        operations.append((value, 0))
        
        # Remove value from its stack
        src_final, _ = pos[value]
        stacks[src_final].pop()
        # Update positions of remaining boxes in src_final
        for j, v in enumerate(stacks[src_final]):
            pos[v] = (src_final, j)
    
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    print("\n".join(out))

solve()
