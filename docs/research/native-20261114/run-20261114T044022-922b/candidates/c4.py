import sys

def solve():
    data = sys.stdin.buffer.read().split()
    it = iter(data)
    n = int(next(it))
    m = int(next(it))
    
    # stacks[i] is a list of box numbers from bottom to top
    stacks = []
    for i in range(m):
        stack = []
        for j in range(n // m):
            stack.append(int(next(it)))
        stacks.append(stack)
    
    # Position map: pos[v] = (stack_index, position_in_stack)
    pos = [None] * (n + 1)
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    operations = []
    
    for value in range(1, n + 1):
        src_i, src_j = pos[value]
        
        if src_j + 1 < len(stacks[src_i]):
            # Need to move boxes above value
            above = stacks[src_i][src_j + 1:]
            
            # Choose destination stack
            # Strategy: find the best destination
            # A good heuristic: minimize the number of boxes that will need to be moved later
            # or choose a stack where we can place them to form a useful sequence
            
            best_dest = -1
            best_score = float('inf')
            
            for dest_i in range(m):
                if dest_i == src_i:
                    continue
                
                # Score based on how well this placement helps
                # Prefer shorter stacks (less work later)
                # Also consider if the top of dest stack relates to our boxes
                score = len(stacks[dest_i])
                
                # Bonus if the top of dest is just below one of our boxes
                if stacks[dest_i]:
                    top_val = stacks[dest_i][-1]
                    for box in above:
                        if box == top_val + 1:
                            score -= 10  # strong bonus for forming sequence
                            break
                
                if score < best_score:
                    best_score = score
                    best_dest = dest_i
            
            if best_dest == -1:
                best_dest = (src_i + 1) % m
            
            operations.append((above[0], best_dest + 1))
            
            # Update state
            moved = stacks[src_i][src_j + 1:]
            del stacks[src_i][src_j + 1:]
            stacks[best_dest].extend(moved)
            
            # Update positions
            for k, box in enumerate(moved):
                pos[box] = (best_dest, len(stacks[best_dest]) - len(moved) + k)
        
        # Carry out value
        operations.append((value, 0))
        
        # Remove value from its stack
        stacks[src_i].pop()
        # Update positions for remaining boxes in src_i
        for j in range(len(stacks[src_i])):
            pos[stacks[src_i][j]] = (src_i, j)
    
    # Output
    out_lines = []
    for v, i in operations:
        out_lines.append(f"{v} {i}")
    print('\n'.join(out_lines))

solve()
