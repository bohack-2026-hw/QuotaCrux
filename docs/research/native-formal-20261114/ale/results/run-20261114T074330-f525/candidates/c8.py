import sys

def solve():
    it = iter(map(int, sys.stdin.buffer.read().split()))
    n, m = next(it), next(it)
    stacks = [[next(it) for _ in range(n // m)] for _ in range(m)]
    
    # Position tracking: pos[v] = (stack_index, position_in_stack)
    pos = [None] * (n + 1)
    for i in range(m):
        for j, v in enumerate(stacks[i]):
            pos[v] = (i, j)
    
    operations = []
    
    def find_stack_of(value):
        return pos[value][0]
    
    def find_pos_in_stack(value):
        return pos[value][1]
    
    for value in range(1, n + 1):
        src = pos[value][0]
        position = pos[value][1]
        
        if position + 1 < len(stacks[src]):
            # Need to move boxes above value
            above = stacks[src][position + 1:]
            
            # Choose destination stack
            # Strategy: prefer empty stacks, then shortest stacks
            # But also consider: the smallest box in 'above' should be accessible soon
            min_above = min(above)
            
            best_dest = -1
            best_score = float('inf')
            
            for j in range(m):
                if j == src:
                    continue
                
                # Score based on:
                # 1. Stack length (shorter is better)
                # 2. Whether this stack contains boxes that need to be taken out before min_above
                # 3. Prefer empty stacks
                
                stack_len = len(stacks[j])
                
                # Count how many boxes in this stack are smaller than min_above
                # (they would need to be removed first, making this a bad choice)
                blocking_boxes = sum(1 for box in stacks[j] if box < min_above and box != value)
                
                score = stack_len * 10 + blocking_boxes * 5
                
                if score < best_score:
                    best_score = score
                    best_dest = j
            
            dest = best_dest
            
            # Perform the move
            operations.append((above[0], dest + 1))
            
            # Update stacks
            moved = stacks[src][position + 1:]
            del stacks[src][position + 1:]
            stacks[dest].extend(moved)
            
            # Update positions
            for k, box in enumerate(moved):
                pos[box] = (dest, len(stacks[dest]) - len(moved) + k)
        
        # Carry out value
        operations.append((value, 0))
        
        # Remove value from its stack
        src = pos[value][0]
        position = pos[value][1]
        assert stacks[src][position] == value
        del stacks[src][position]
        
        # Update positions of all boxes in this stack after position
        for k in range(position, len(stacks[src])):
            pos[stacks[src][k]] = (src, k)
    
    # Output operations
    out_lines = []
    for v, i in operations:
        out_lines.append(f"{v} {i}")
    print('\n'.join(out_lines))

solve()
