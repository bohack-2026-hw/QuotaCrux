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
    
    # Position tracking: pos[v] = (stack_idx, position_in_stack)
    pos = [None] * (n + 1)
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    operations = []
    
    for value in range(1, n + 1):
        src_i, src_pos = pos[value]
        if src_pos + 1 < len(stacks[src_i]):
            # Need to move boxes above value
            above = stacks[src_i][src_pos + 1:]
            # Choose destination stack
            # Strategy: pick the stack that minimizes some cost metric
            best_dest = -1
            best_score = float('inf')
            for j in range(m):
                if j == src_i:
                    continue
                # Score based on how well the moved boxes fit
                # Prefer stacks where the top box is smaller (so our boxes go on top nicely)
                # Also prefer shorter stacks
                if len(stacks[j]) == 0:
                    score = 0
                else:
                    top_box = stacks[j][-1]
                    # If top box is small, good; if large, bad
                    # We want to minimize future disruption
                    score = len(stacks[j]) * 10 + abs(top_box - above[0])
                if score < best_score:
                    best_score = score
                    best_dest = j
            
            if best_dest == -1:
                best_dest = (src_i + 1) % m
            
            # Move above boxes to best_dest
            dest_i = best_dest
            operations.append((above[0], dest_i + 1))
            
            # Update positions
            for k, v in enumerate(above):
                pos[v] = (dest_i, len(stacks[dest_i]) + k)
            stacks[dest_i].extend(above)
            del stacks[src_i][src_pos + 1:]
        
        # Carry out value
        operations.append((value, 0))
        stacks[src_i].pop()
        # Update positions for remaining boxes in src_i
        for j in range(src_pos):
            v = stacks[src_i][j]
            pos[v] = (src_i, j)
    
    # Output
    out_lines = []
    for v, i in operations:
        out_lines.append(f"{v} {i}")
    sys.stdout.write("\n".join(out_lines) + "\n")

solve()