import sys

def solve():
    data = list(map(int, sys.stdin.buffer.read().split()))
    if not data:
        return
    n, m = data[0], data[1]
    k = n // m
    stacks = []
    idx = 2
    for i in range(m):
        stacks.append(data[idx:idx+k])
        idx += k
    
    # Track position of each box
    pos = {}  # box -> (stack_idx, height)
    for i, stack in enumerate(stacks):
        for j, box in enumerate(stack):
            pos[box] = (i, j)
    
    operations = []
    total_energy = 0
    
    for value in range(1, n + 1):
        src, pos_in_src = pos[value]
        
        # Check if value is at the top of its stack
        if pos_in_src == len(stacks[src]) - 1:
            # Can carry out directly
            operations.append((value, 0))
            # Remove from stack and update positions
            del stacks[src][-1]
            del pos[value]
            continue
        
        # Need to move boxes above value to another stack
        boxes_above = stacks[src][pos_in_src+1:]
        num_above = len(boxes_above)
        
        # Choose destination stack to minimize future cost
        # Strategy: choose the stack that will cause least disruption
        best_dest = None
        best_score = float('inf')
        
        for dest in range(m):
            if dest == src:
                continue
            
            # Score based on how many boxes are already in this stack
            # and their relative order with respect to the boxes we're moving
            current_stack = stacks[dest]
            
            # Count conflicts: boxes in current stack that are smaller than some boxes being moved
            # but larger than others - this creates more work later
            conflicts = 0
            for box in current_stack:
                for moving_box in boxes_above:
                    if box < moving_box:
                        # This box needs to be carried out before moving_box
                        # If it's below moving_box after merge, that's fine
                        # If it's above, that's a conflict
                        pass
            
            # Simpler heuristic: prefer shorter stacks to keep options open
            score = len(current_stack)
            
            # Additional penalty if the top of dest stack has a box that should come after our boxes
            if current_stack:
                top_box = current_stack[-1]
                min_moving = min(boxes_above)
                max_moving = max(boxes_above)
                if top_box > min_moving:
                    score += 5  # Penalty for potential ordering issues
            
            if score < best_score:
                best_score = score
                best_dest = dest
        
        # Move boxes above value to best_dest
        energy = num_above + 1
        total_energy += energy
        operations.append((boxes_above[0], best_dest + 1))
        
        # Update stacks
        stacks[best_dest].extend(boxes_above)
        del stacks[src][pos_in_src+1:]
        
        # Update positions
        for i, box in enumerate(boxes_above):
            pos[box] = (best_dest, len(stacks[best_dest]) - num_above + i)
        
        # Now value should be at the top of src
        operations.append((value, 0))
        del stacks[src][-1]
        del pos[value]
    
    # Output operations
    out_lines = []
    for v, i in operations:
        out_lines.append(f"{v} {i}")
    print('\n'.join(out_lines))

solve()
