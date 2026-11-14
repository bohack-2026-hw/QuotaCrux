import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    n, m = data[0], data[1]
    idx = 2
    stacks = []
    for i in range(m):
        s = data[idx:idx + n // m]
        idx += n // m
        stacks.append(s)
    
    # Build position map: box -> (stack_idx, pos_in_stack)
    pos_map = {}
    for si in range(m):
        for pi, val in enumerate(stacks[si]):
            pos_map[val] = (si, pi)
    
    operations = []
    
    for value in range(1, n + 1):
        src, pos = pos_map[value]
        stack = stacks[src]
        
        if pos + 1 < len(stack):
            # Need to move boxes above value
            above = stack[pos + 1:]
            
            # Choose best destination: prefer stacks where top element is large
            # and the stack is short
            best_dest = -1
            best_score = float('inf')
            for j in range(m):
                if j == src:
                    continue
                dest_stack = stacks[j]
                # Score: prefer shorter stacks, and stacks with larger top elements
                # A good destination has a small length and its top is not too small
                # relative to the boxes we're moving
                min_above = min(above)
                if len(dest_stack) == 0:
                    score = 0
                else:
                    top = dest_stack[-1]
                    # If top > min_above, it's good because after placing,
                    # the smallest of what we moved will be on top of something smaller
                    # Actually we want to minimize future moves.
                    # Heuristic: prefer stacks whose current top is greater than all of 'above'
                    # This way 'above' sits cleanly on top.
                    if top >= max(above):
                        score = len(dest_stack) * 1.0
                    else:
                        score = len(dest_stack) * 10.0 + (max(above) - top)
                if score < best_score:
                    best_score = score
                    best_dest = j
            
            # Move the entire block above
            operations.append((above[0], best_dest + 1))
            
            # Update state
            moved = stack[pos + 1:]
            del stack[pos + 1:]
            stacks[best_dest].extend(moved)
            
            # Update pos_map for moved boxes
            base = len(stacks[best_dest]) - len(moved)
            for k, mv in enumerate(moved):
                pos_map[mv] = (best_dest, base + k)
        
        # Carry out value
        operations.append((value, 0))
        
        # Remove from stack
        stack.pop()
        # Update pos_map for remaining boxes in this stack
        for pi in range(pos):
            pos_map[stack[pi]] = (src, pi)
    
    out = []
    for v, i in operations:
        out.append(f"{v} {i}")
    sys.stdout.write("\n".join(out) + "\n")

solve()
